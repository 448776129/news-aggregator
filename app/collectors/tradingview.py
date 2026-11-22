"""TradingView：公开新闻头条接口。"""
from __future__ import annotations

from urllib.parse import quote

from ..config import TRADINGVIEW_SYMBOLS
from ..http_client import get_json
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, stable_id
from .base import BaseCollector


class TradingViewCollector(BaseCollector):
    key = "tradingview"

    ENDPOINTS = (
        "https://news-headlines.tradingview.com/v2/headlines",
        "https://news-headlines.tradingview.com/v2/view/headlines/symbol",
    )

    def collect(self, date: str) -> list[NewsItem]:
        rows: list[dict] = []
        requests = [(url, None) for url in self.ENDPOINTS]
        requests += [
            (self.ENDPOINTS[1], {"client": "web", "lang": "en", "symbol": quote(symbol, safe=":")})
            for symbol in TRADINGVIEW_SYMBOLS
        ]
        for url, extra in requests:
            params = {"client": "web", "lang": "en"}
            if extra:
                params.update(extra)
            data = get_json(url, params=params)
            if isinstance(data, dict):
                rows = [r for r in (data.get("items") or []) if isinstance(r, dict)]
            if rows:
                break
        items: list[NewsItem] = []
        for row in rows:
            title = clean_html(row.get("title", ""), 300)
            if not title:
                continue
            raw_id = row.get("id") or title
            story = row.get("storyPath", "")
            url = row.get("link") or (f"https://www.tradingview.com{story}" if story else "")
            dt = parse_datetime(row.get("published"))
            symbols = [s.get("symbol", "") for s in (row.get("relatedSymbols") or []) if isinstance(s, dict)]
            items.append(
                NewsItem(
                    id=stable_id("tradingview", raw_id),
                    title=title,
                    url=url,
                    summary=clean_html(row.get("description", row.get("summary", "")), 600),
                    author=str(row.get("source", "")),
                    published_at=iso(dt),
                    extra={"urgency": row.get("urgency", ""), "symbols": symbols},
                )
            )
        return items
