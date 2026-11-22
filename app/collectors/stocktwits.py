"""Stocktwits：公开个股消息流（无需 API Key）。"""
from __future__ import annotations

from ..config import STOCKTWITS_SYMBOLS
from ..http_client import get_json
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, stable_id
from .base import BaseCollector


class StocktwitsCollector(BaseCollector):
    key = "stocktwits"

    def collect(self, date: str) -> list[NewsItem]:
        items: list[NewsItem] = []
        requests = [(symbol, f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json") for symbol in STOCKTWITS_SYMBOLS]
        requests.append(("", "https://api.stocktwits.com/api/2/streams/trending.json"))
        for symbol, url in requests:
            data = get_json(url, headers={"Accept": "application/json"})
            if not isinstance(data, dict):
                continue
            for message in data.get("messages", []) or []:
                if not isinstance(message, dict):
                    continue
                body = clean_html(message.get("body", ""), 600)
                if not body:
                    continue
                raw_id = message.get("id") or body[:60]
                dt = parse_datetime(message.get("created_at"))
                user = message.get("user") or {}
                entities = message.get("entities") or {}
                sentiment = entities.get("sentiment") or {}
                symbols = [s.get("symbol", "") for s in (message.get("symbols") or []) if isinstance(s, dict)]
                items.append(
                    NewsItem(
                        id=stable_id("stocktwits", raw_id),
                        title=body[:120],
                        url=(
                            f"https://stocktwits.com/symbol/{symbol}"
                            if symbol
                            else f"https://stocktwits.com/message/{raw_id}"
                        ),
                        summary=body,
                        author=user.get("username", "") if isinstance(user, dict) else "",
                        published_at=iso(dt),
                        extra={
                            "sentiment": sentiment.get("basic") if isinstance(sentiment, dict) else "",
                            "symbols": symbols,
                        },
                    )
                )
        return items
