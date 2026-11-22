"""按天、按分类归档 JSON，并维护索引。支持同一天多次抓取增量合并。"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from typing import Any

from .config import CATEGORIES, DATA_DIR, TZ
from .models import NewsItem, SourceResult
from .utils import iso, local_now

logger = logging.getLogger("newsagg.storage")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def category_path(date: str, category: str) -> str:
    return os.path.join(DATA_DIR, date, f"{category}.json")


def index_path() -> str:
    return os.path.join(DATA_DIR, "index.json")


def load_day(date: str, category: str) -> dict[str, Any] | None:
    path = category_path(date, category)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def merge_items(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """按 id 去重；已入库的 id 保留原始记录，避免每 5 分钟刷新 fetched_at。"""
    merged: dict[str, dict] = {}
    # 先放旧数据，后者只在 id 不存在时补入
    for item in list(existing) + list(incoming):
        if not isinstance(item, dict):
            continue
        key = item.get("id") or f"tmp:{item.get('title', '')}"
        if key not in merged:
            merged[key] = item
    items = list(merged.values())
    items.sort(key=lambda x: (x.get("published_at") or x.get("fetched_at") or ""), reverse=True)
    return items


def save_day(
    date: str,
    category: str,
    items: list[NewsItem],
    source_results: list[SourceResult] | None = None,
) -> dict[str, Any]:
    old = load_day(date, category)
    old_items = old.get("items", []) if old else []
    merged = merge_items(old_items, [item.to_dict() for item in items])
    # 按新闻发布时间归档：剔除历史遗留的“采集日归档”条目。
    # 老数据没有 published_date 时保留，继续按采集日兜底。
    merged = [
        item for item in merged
        if not item.get("published_date") or item.get("published_date") == date
    ]

    # 合并来源状态：同一来源保留最近一次结果
    sources: dict[str, dict] = {}
    if old:
        for row in old.get("sources", []) or []:
            if isinstance(row, dict) and row.get("name"):
                sources[row["name"]] = row
    if source_results:
        for result in source_results:
            sources[result.name] = result.to_dict()

    sorted_sources = sorted(sources.values(), key=lambda x: x.get("name", ""))
    # 内容与来源状态都没变化时不重写文件，避免每 5 分钟产生空提交。
    if old and old.get("items") == merged and old.get("sources") == sorted_sources:
        return old

    payload = {
        "date": date,
        "category": category,
        "category_name": CATEGORIES.get(category, category),
        "timezone": str(TZ),
        "generated_at": iso(local_now()),
        "count": len(merged),
        "sources": sorted_sources,
        "items": merged,
    }
    _write_json(category_path(date, category), payload)
    return payload


def read_index() -> dict[str, Any]:
    path = index_path()
    if not os.path.exists(path):
        return {"updated_at": "", "dates": [], "categories": [], "entries": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {"updated_at": "", "dates": [], "categories": [], "entries": {}}


def rebuild_index() -> dict[str, Any]:
    entries: dict[str, Any] = {}
    if os.path.isdir(DATA_DIR):
        for date in sorted(os.listdir(DATA_DIR)):
            if not DATE_RE.match(date):
                continue
            folder = os.path.join(DATA_DIR, date)
            if not os.path.isdir(folder):
                continue
            for filename in sorted(os.listdir(folder)):
                if not filename.endswith(".json"):
                    continue
                category = filename[:-5]
                path = os.path.join(folder, filename)
                try:
                    with open(path, encoding="utf-8") as fh:
                        data = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    continue
                entries.setdefault(date, {})[category] = {
                    "count": data.get("count", len(data.get("items", []))),
                    "file": f"data/{date}/{filename}",
                    "generated_at": data.get("generated_at", ""),
                }
    old_index = read_index()
    new_dates = sorted(entries.keys(), reverse=True)
    new_categories = sorted({c for v in entries.values() for c in v})
    # 索引内容不变时不重写，避免 updated_at 每次刷新造成无意义提交。
    if (
        old_index.get("dates") == new_dates
        and old_index.get("categories") == new_categories
        and old_index.get("entries") == entries
    ):
        return old_index

    payload = {
        "updated_at": iso(local_now()),
        "dates": new_dates,
        "categories": new_categories,
        "entries": entries,
    }
    _write_json(index_path(), payload)
    return payload


def list_dates() -> list[str]:
    return read_index().get("dates", [])


def list_categories(date: str | None = None) -> list[str]:
    index = read_index()
    if date:
        return sorted(index.get("entries", {}).get(date, {}).keys())
    return index.get("categories", [])
