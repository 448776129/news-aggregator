"""Alpaca News：需要 API Key，未配置时自动跳过（不视为失败）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..config import ALPACA_API_KEY, ALPACA_DATA_URL, ALPACA_SECRET_KEY
from ..http_client import get_json
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, stable_id
from .base import BaseCollector


class AlpacaCollector(BaseCollector):
    key = "alpaca"

    @property
    def available(self) -> bool:
        return bool(ALPACA_API_KEY and ALPACA_SECRET_KEY)

    def collect(self, date: str) -> list[NewsItem]:
        if not self.available:
            return []
        try:
            next_day = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            next_day = date
        data = get_json(
            f"{ALPACA_DATA_URL}/v1beta1/news",
            params={"sort": "desc", "limit": 50, "start": date, "end": next_day, "include_content": "true"},
            headers={
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
            },
        )
        if not isinstance(data, dict):
            return []
        items: list[NewsItem] = []
        for row in data.get("news", []) or []:
            if not isinstance(row, dict):
                continue
            title = clean_html(row.get("headline", ""), 300)
            if not title:
                continue
            dt = parse_datetime(row.get("created_at"))
            full_content = clean_html(row.get("content", ""))
            summary = clean_html(row.get("summary", "")) or full_content
            items.append(
                NewsItem(
                    id=stable_id("alpaca", row.get("id") or title),
                    title=title,
                    url=str(row.get("url", "")),
                    summary=summary,
                    content=full_content,
                    author=str(row.get("author", "")),
                    published_at=iso(dt),
                    extra={"source": row.get("source", ""), "symbols": row.get("symbols", [])},
                )
            )
        return items
