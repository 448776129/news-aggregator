"""雅虎新闻 / Yahoo Finance：公开 RSS。"""
from __future__ import annotations

from ..config import YAHOO_SYMBOLS
from ..http_client import get_text
from ..models import NewsItem
from ..utils import iso, parse_datetime, parse_feed, stable_id
from .base import BaseCollector


class YahooCollector(BaseCollector):
    key = "yahoo"

    def collect(self, date: str) -> list[NewsItem]:
        urls = ["https://finance.yahoo.com/rss/topstories"]
        urls += [f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={s}" for s in YAHOO_SYMBOLS]
        items: list[NewsItem] = []
        seen: set[str] = set()
        for url in urls:
            text = get_text(url)
            if not text:
                continue
            for entry in parse_feed(text):
                key = entry.get("url") or entry["title"]
                if key in seen:
                    continue
                seen.add(key)
                dt = parse_datetime(entry.get("published"))
                items.append(
                    NewsItem(
                        id=stable_id("yahoo", key),
                        title=entry["title"],
                        url=entry.get("url", ""),
                        summary=entry.get("summary", ""),
                        author=entry.get("author", ""),
                        published_at=iso(dt),
                    )
                )
        return items
