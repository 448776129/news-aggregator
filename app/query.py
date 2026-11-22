"""查询层：按日期 + 分类读取数据，支持本地优先、GitHub 远端回退。"""
from __future__ import annotations

import json
import logging
from typing import Any

from . import storage
from .config import CATEGORIES, GITHUB_RAW_BASE_URL, GITHUB_REPO, GITHUB_TOKEN
from .http_client import get_text
from .utils import today_str

logger = logging.getLogger("newsagg.query")


def _remote_text(rel_path: str) -> str | None:
    if GITHUB_RAW_BASE_URL:
        text = get_text(f"{GITHUB_RAW_BASE_URL}/{rel_path}")
        if text:
            return text
    if GITHUB_REPO and GITHUB_TOKEN:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{rel_path}"
        return get_text(url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.raw+json"})
    return None


def load_payload(date: str, category: str) -> dict[str, Any] | None:
    local = storage.load_day(date, category)
    if local is not None:
        return local
    text = _remote_text(f"data/{date}/{category}.json")
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def list_dates() -> list[str]:
    dates = storage.list_dates()
    if dates:
        return dates
    text = _remote_text("data/index.json")
    if text:
        try:
            return json.loads(text).get("dates", [])
        except json.JSONDecodeError:
            pass
    return []


def resolve_date(date: str | None) -> str:
    if not date or date.lower() in ("latest", "today"):
        dates = list_dates()
        return dates[0] if dates else today_str()
    return date


def list_categories(date: str | None = None) -> list[str]:
    if date:
        index = storage.read_index()
        cats = sorted(index.get("entries", {}).get(date, {}).keys())
        if cats:
            return cats
        cats = [c for c in CATEGORIES if load_payload(date, c)]
        if cats:
            return cats
    return sorted(CATEGORIES)


def query_news(
    date: str | None = None,
    category: str | None = None,
    source: str | None = None,
    keyword: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """核心查询：返回指定日期、指定分类（或全部分类）的新闻。"""
    target_date = resolve_date(date)
    categories = [category] if category else list_categories(target_date)
    items: list[dict[str, Any]] = []
    keyword_lower = keyword.lower() if keyword else ""
    for cat in categories:
        payload = load_payload(target_date, cat)
        if not payload:
            continue
        for raw in payload.get("items", []) or []:
            if not isinstance(raw, dict):
                continue
            if source and raw.get("source") != source:
                continue
            if keyword_lower:
                haystack = f"{raw.get('title', '')} {raw.get('summary', '')}".lower()
                if keyword_lower not in haystack:
                    continue
            item = dict(raw)
            item.setdefault("category", cat)
            items.append(item)
    items.sort(key=lambda x: (x.get("published_at") or x.get("fetched_at") or ""), reverse=True)
    if limit:
        items = items[:limit]
    return {
        "date": target_date,
        "category": category or "all",
        "count": len(items),
        "items": items,
    }
