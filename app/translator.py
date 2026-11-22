"""新闻标题/摘要中文翻译。

使用 OpenAI 兼容的 Chat Completions 接口：
- 默认关闭思考模式（thinking=disabled / reasoning_effort=none / temperature=0）
- 限流或额度耗尽时按 TRANSLATE_MODELS 顺序自动切换模型
- 原文 title / summary / content 全部保留，译文写入 title_zh / summary_zh
- 翻译失败只记录警告，不影响采集与归档主流程
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from .config import (
    TRANSLATE_API_KEY,
    TRANSLATE_BATCH_SIZE,
    TRANSLATE_BASE_URL,
    TRANSLATE_ENABLED,
    TRANSLATE_MAX_ITEMS,
    TRANSLATE_MODELS,
    TRANSLATE_TARGET_LANG,
)
from .models import NewsItem

logger = logging.getLogger("newsagg.translate")

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_QUOTA_WORDS = (
    "ratelimit", "rate_limit", "rate limit", "quota", "insufficient",
    "exceed", "throttle", "429", "402", "403", "balance", "credit",
)
_model_index = 0
_no_key_warned = False


def _is_chinese(text: str) -> bool:
    """判断文本是否已是中文，避免重复翻译。"""
    if not text:
        return True
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    cjk = sum(1 for c in letters if _CJK_RE.match(c))
    return cjk / len(letters) > 0.25


def _quota_error(resp: requests.Response | None, exc: Exception | None = None) -> bool:
    if exc is not None:
        return False
    if resp is None:
        return False
    if resp.status_code in (402, 403, 429):
        return True
    try:
        body = resp.text.lower()
    except Exception:
        return False
    return any(word in body for word in _QUOTA_WORDS)


def _next_model() -> str | None:
    """轮换到下一个可用模型；全部失败返回 None。"""
    global _model_index
    if not TRANSLATE_MODELS:
        return None
    for _ in range(len(TRANSLATE_MODELS)):
        model = TRANSLATE_MODELS[_model_index % len(TRANSLATE_MODELS)]
        _model_index = (_model_index + 1) % len(TRANSLATE_MODELS)
        return model
    return None


def _current_model() -> str | None:
    if not TRANSLATE_MODELS:
        return None
    return TRANSLATE_MODELS[_model_index % len(TRANSLATE_MODELS)]


def _advance_model() -> None:
    global _model_index
    _model_index = (_model_index + 1) % len(TRANSLATE_MODELS)


def _post_translate(
    model: str,
    texts: list[dict[str, str]],
    json_mode: bool = True,
    reasoning: str = "none",
    include_thinking: bool = True,
):
    """调用一次 Chat Completions，返回 (content, resp, exc)。"""
    system = (
        f"你是专业财经新闻翻译。把给定的新闻标题与摘要翻译成{TRANSLATE_TARGET_LANG}。"
        "保留公司名、人名、股票代码与数字，不要扩写、不要解释。"
        '仅输出 JSON：{"items":[{"id":"...","title":"...","summary":"..."}]}。'
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"items": texts}, ensure_ascii=False)},
        ],
        "temperature": 0,
        # 最低思考模式：不同兼容层都带上，能识别哪个用哪个
        "reasoning_effort": reasoning,
        "max_tokens": 4096,
    }
    if include_thinking:
        payload["thinking"] = {"type": "disabled"}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        resp = requests.post(
            f"{TRANSLATE_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {TRANSLATE_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
        if resp.status_code != 200:
            return None, resp, None
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, resp, None
    except Exception as exc:  # noqa: BLE001 - 翻译失败不能影响采集
        return None, None, exc


def _extract_json(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def translate_items(items: list[NewsItem], existing: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """为需要翻译的条目补上 title_zh / summary_zh。

    existing: id -> {"title_zh": ..., "summary_zh": ...}，用于复用上次已翻译结果。
    返回本次翻译统计。
    """
    global _no_key_warned
    stats = {
        "enabled": TRANSLATE_ENABLED,
        "translated": 0,
        "reused": 0,
        "failed": 0,
        "deferred": False,
        "model": "",
    }

    if not TRANSLATE_ENABLED:
        return stats
    if not TRANSLATE_API_KEY:
        if not _no_key_warned:
            logger.warning("未配置 TRANSLATE_API_KEY，跳过标题/摘要翻译")
            _no_key_warned = True
        return stats
    if not items:
        return stats

    existing = existing or {}
    pending: list[dict[str, str]] = []
    for item in items:
        old = existing.get(item.id, {})
        if not item.title_zh and old.get("title_zh"):
            item.title_zh = old["title_zh"]
        if not item.summary_zh and old.get("summary_zh"):
            item.summary_zh = old["summary_zh"]
        if old.get("title_zh") or old.get("summary_zh"):
            stats["reused"] += 1

        title_needed = bool(item.title) and not item.title_zh and not _is_chinese(item.title)
        summary_needed = bool(item.summary) and not item.summary_zh and not _is_chinese(item.summary)
        if title_needed or summary_needed:
            pending.append({
                "id": item.id,
                "title": item.title if title_needed else "",
                "summary": item.summary if summary_needed else "",
            })

    if not pending:
        return stats

    # 限制单次翻译量，保证每 5 分钟的定时任务能在超时前结束。
    if TRANSLATE_MAX_ITEMS and len(pending) > TRANSLATE_MAX_ITEMS:
        pending = pending[:TRANSLATE_MAX_ITEMS]
        stats["deferred"] = True

    by_id = {item.id: item for item in items}
    # 同一模型的兼容配置：先 JSON 模式 + 不思考；不支持就降为 low，再去掉 response_format。
    configs = (
        (True, "none", True),
        (True, "low", True),
        (True, "low", False),
        (False, "none", True),
        (False, "low", True),
        (False, "low", False),
    )
    for start in range(0, len(pending), TRANSLATE_BATCH_SIZE):
        batch = pending[start:start + TRANSLATE_BATCH_SIZE]
        done = False
        tried = 0
        while not done and tried < len(TRANSLATE_MODELS):
            model = _current_model()
            if not model:
                break
            quota = False
            for json_mode, reasoning, include_thinking in configs:
                content, resp, exc = _post_translate(
                    model, batch, json_mode=json_mode, reasoning=reasoning,
                    include_thinking=include_thinking,
                )
                if content:
                    parsed = _extract_json(content)
                    rows = parsed.get("items") if parsed else None
                    if isinstance(rows, list):
                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            target = by_id.get(str(row.get("id", "")))
                            if not target:
                                continue
                            if row.get("title"):
                                target.title_zh = str(row["title"]).strip()
                            if row.get("summary"):
                                target.summary_zh = str(row["summary"]).strip()
                            target.extra["translate_model"] = model
                            stats["translated"] += 1
                        stats["model"] = model
                        done = True
                        break
                    logger.warning("模型 %s 翻译返回格式异常，换配置重试", model)
                if _quota_error(resp, exc):
                    quota = True
                    break
                body = resp.text if resp is not None else ""
                if "reasoning_effort" in body or "thinking" in body:
                    # 该模型不支持当前思考参数配置，换下一个配置重试同一模型
                    continue
                logger.warning(
                    "模型 %s 翻译失败: %s", model,
                    (exc or (body[:200] if body else "未知错误")),
                )
                break
            _advance_model()
            tried += 1
            if quota:
                logger.warning("模型 %s 额度/限流，切换到下一个模型", model)
                time.sleep(1)
        if not done:
            stats["failed"] += len(batch)

    return stats
