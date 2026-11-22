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
    """按 id 去重；同一 id 保留 fetched_at 更新的那条。"""
    merged: dict[str, dict] = {}
    for item in list(existing) + list(incoming):
        if not isinstance(item, dict):
            continue
        key = item.get("id") or f"tmp:{item.get('title', '')}"
        old = merged.get(key)
        if old is None or str(item.get("fetched_at", "")) >= str(old.get("fetched_at", "")):
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

    payload = {
        "date": date,
        "category": category,
        "category_name": CATEGORIES.get(category, category),
        "timezone": str(TZ),
        "generated_at": iso(local_now()),
        "count": len(merged),
        "sources": sorted(sources.values(), key=lambda x: x.get("name", "")),
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
    payload = {
        "updated_at": iso(local_now()),
        "dates": sorted(entries.keys(), reverse=True),
        "categories": sorted({c for v in entries.values() for c in v}),
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
