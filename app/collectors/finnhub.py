"""Finnhub News：需要 API Key，未配置时自动跳过。"""
from __future__ import annotations

from ..config import FINNHUB_API_KEY, FINNHUB_API_URL, FINNHUB_CATEGORY
from ..http_client import get_json
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, stable_id
from .base import BaseCollector


class FinnhubCollector(BaseCollector):
    key = "finnhub"

    @property
    def available(self) -> bool:
        return bool(FINNHUB_API_KEY)

    def collect(self, date: str) -> list[NewsItem]:
        if not self.available:
            return []
        data = get_json(
            FINNHUB_API_URL,
            params={"category": FINNHUB_CATEGORY, "token": FINNHUB_API_KEY},
        )
        if not isinstance(data, list):
            return []

        items: list[NewsItem] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            title = clean_html(row.get("headline", ""), 300)
            if not title:
                continue
            dt = parse_datetime(row.get("datetime"))
            summary = clean_html(row.get("summary", ""))
            items.append(
                NewsItem(
                    id=stable_id("finnhub", row.get("id") or title),
                    title=title,
                    url=str(row.get("url", "")),
                    summary=summary,
                    content=summary,  # Finnhub 只提供摘要，原文与摘要同文
                    author=str(row.get("source", "")),
                    published_at=iso(dt),
                    extra={
                        "source": str(row.get("source", "")),
                        "category": str(row.get("category", "")),
                        "related": str(row.get("related", "")),
                        "image": str(row.get("image", "")) or None,
                    },
                )
            )
        return items
