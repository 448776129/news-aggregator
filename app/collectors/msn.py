"""微软 MSN：MSN 无稳定公开 RSS，使用 Bing News RSS（微软新闻源）作为等价入口。"""
from __future__ import annotations

from urllib.parse import quote

from ..config import BING_QUERIES
from ..http_client import get_text
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, parse_feed, stable_id
from .base import BaseCollector


class MsnCollector(BaseCollector):
    key = "msn"

    def collect(self, date: str) -> list[NewsItem]:
        urls = [f"https://www.bing.com/news/search?q={quote(q)}&format=rss&mkt=en-US" for q in BING_QUERIES]
        urls += [
            "https://www.msn.com/en-us/news/rss",
            "https://news.msn.com/rss/microsoftnews.aspx",
        ]
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
                        id=stable_id("msn", key),
                        title=entry["title"],
                        url=entry.get("url", ""),
                        summary=clean_html(entry.get("summary", "")),
                        author=entry.get("author", ""),
                        published_at=iso(dt),
                    )
                )
        return items
