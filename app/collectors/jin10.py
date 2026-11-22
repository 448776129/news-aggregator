"""金十数据：优先开放平台 API（需 secret-key），否则用公开快讯脚本。"""
from __future__ import annotations

import json
import re

from ..config import JIN10_SECRET_KEY
from ..http_client import get_json, get_text
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, pick, stable_id
from .base import BaseCollector


class Jin10Collector(BaseCollector):
    key = "jin10"

    OPEN_API = "https://open-data-api.jin10.com/data-api/flash"
    PUBLIC_JS = "https://www.jin10.com/flash_newest.js"

    def collect(self, date: str) -> list[NewsItem]:
        rows: list[dict] = []
        if JIN10_SECRET_KEY:
            data = get_json(
                self.OPEN_API,
                params={"category": "1,2,3,4,5"},
                headers={"secret-key": JIN10_SECRET_KEY},
            )
            rows = self._extract_rows(data)
        if not rows:
            text = get_text(self.PUBLIC_JS)
            rows = self._parse_js(text) if text else []
        return self._to_items(rows)

    @staticmethod
    def _extract_rows(data) -> list[dict]:
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            for key in ("data", "list", "items", "flash"):
                value = data.get(key)
                if isinstance(value, list):
                    return [r for r in value if isinstance(r, dict)]
        return []

    @staticmethod
    def _parse_js(text: str) -> list[dict]:
        match = re.search(r"=\s*(\[[\s\S]*\])\s*;?", text)
        if not match:
            return []
        try:
            value = json.loads(match.group(1))
            return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _to_items(rows: list[dict]) -> list[NewsItem]:
        items: list[NewsItem] = []
        for row in rows:
            detail = row.get("data") if isinstance(row.get("data"), dict) else {}
            title = clean_html(pick(detail, "title", default=""), 300)
            content = clean_html(pick(detail, "content", default=""), 600)
            if not title:
                title = content[:80] or "金十快讯"
            raw_id = pick(row, "id", default=title)
            dt = parse_datetime(pick(row, "time", "created_at", default=""))
            items.append(
                NewsItem(
                    id=stable_id("jin10", raw_id),
                    title=title,
                    url=f"https://www.jin10.com/#/flash/{raw_id}",
                    summary=content,
                    author=str(pick(detail, "source", default="")),
                    published_at=iso(dt),
                    extra={"important": row.get("important", 0)},
                )
            )
        return items
