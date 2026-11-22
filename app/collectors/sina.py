"""新浪财经：滚动新闻 JSON API，失败时回退 RSS。"""
from __future__ import annotations

from ..http_client import get_json, get_text
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, parse_feed, pick, stable_id
from .base import BaseCollector


class SinaCollector(BaseCollector):
    key = "sina"

    API = "https://feed.mix.sina.com.cn/api/roll/get"
    RSS = "https://rss.sina.com.cn/finance/rollnews.xml"

    def collect(self, date: str) -> list[NewsItem]:
        items = self._from_api()
        if not items:
            items = self._from_rss()
        return items

    def _from_api(self) -> list[NewsItem]:
        data = get_json(
            self.API,
            params={"pageid": 153, "lid": 2516, "k": "", "num": 50, "page": 1},
            headers={"Referer": "https://finance.sina.com.cn/"},
        )
        if not data:
            return []
        rows = pick(data, "result", default={}) or {}
        rows = pick(rows, "data", default=[]) or []
        items: list[NewsItem] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = clean_html(pick(row, "title", "brief", default=""), 300)
            if not title:
                continue
            url = str(pick(row, "url", "link", default=""))
            raw_id = pick(row, "id", "url", default=url)
            dt = parse_datetime(pick(row, "ctime", "pub_date", default=""))
            items.append(
                NewsItem(
                    id=stable_id("sina", raw_id),
                    title=title,
                    url=url,
                    summary=clean_html(pick(row, "intro", "description", default="")),
                    author=str(pick(row, "media_name", "author", default="")),
                    published_at=iso(dt),
                )
            )
        return items

    def _from_rss(self) -> list[NewsItem]:
        text = get_text(self.RSS)
        if not text:
            return []
        items: list[NewsItem] = []
        for entry in parse_feed(text):
            dt = parse_datetime(entry.get("published"))
            items.append(
                NewsItem(
                    id=stable_id("sina", entry.get("url") or entry["title"]),
                    title=entry["title"],
                    url=entry.get("url", ""),
                    summary=clean_html(entry.get("summary", "")),
                    author=entry.get("author", ""),
                    published_at=iso(dt),
                )
            )
        return items
