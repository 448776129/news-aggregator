"""财联社电报：nodeapi 公开接口。"""
from __future__ import annotations

from ..http_client import get_json
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, pick, stable_id
from .base import BaseCollector


class ClsCollector(BaseCollector):
    key = "cls"

    ENDPOINTS = (
        "https://www.cls.cn/nodeapi/telegraphList",
        "https://www.cls.cn/nodeapi/updateTelegraphList",
    )
    HEADERS = {"Referer": "https://www.cls.cn/telegraph", "Origin": "https://www.cls.cn"}
    PARAMS = {"app": "CailianpressWeb", "os": "web", "sv": "8.4.6", "rn": 100}

    def collect(self, date: str) -> list[NewsItem]:
        rows: list[dict] = []
        for url in self.ENDPOINTS:
            data = get_json(url, params=self.PARAMS, headers=self.HEADERS)
            if isinstance(data, dict):
                payload = data.get("data") or {}
                if isinstance(payload, dict):
                    for key in ("roll_data", "list", "data"):
                        value = payload.get(key)
                        if isinstance(value, list):
                            rows = [r for r in value if isinstance(r, dict)]
                            break
            if rows:
                break
        items: list[NewsItem] = []
        for row in rows:
            content = clean_html(pick(row, "content", "brief", default=""), 600)
            title = clean_html(pick(row, "title", default=""), 300) or content[:80]
            if not title:
                continue
            raw_id = pick(row, "id", "shareurl", default=title)
            dt = parse_datetime(pick(row, "ctime", "time", default=""))
            url = str(pick(row, "shareurl", default="")) or f"https://www.cls.cn/detail/{raw_id}"
            items.append(
                NewsItem(
                    id=stable_id("cls", raw_id),
                    title=title,
                    url=url,
                    summary=content if title != content[:80] else "",
                    published_at=iso(dt),
                    extra={"level": row.get("level", ""), "type": row.get("type", "")},
                )
            )
        return items
