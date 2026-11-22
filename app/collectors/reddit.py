"""Reddit：公开 .json 列表接口（需自定义 User-Agent，无需 OAuth）。"""
from __future__ import annotations

from ..config import REDDIT_SUBS
from ..http_client import get_json
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, stable_id
from .base import BaseCollector


class RedditCollector(BaseCollector):
    key = "reddit"
    HEADERS = {"User-Agent": f"news-aggregator/1.0 (by /u/open-source)", "Accept": "application/json"}

    def collect(self, date: str) -> list[NewsItem]:
        items: list[NewsItem] = []
        for sub in REDDIT_SUBS:
            data = None
            for base in ("https://www.reddit.com", "https://old.reddit.com"):
                data = get_json(
                    f"{base}/r/{sub}/new.json",
                    params={"limit": 50, "raw_json": 1},
                    headers=self.HEADERS,
                    timeout=6,
                )
                if isinstance(data, dict) and (data.get("data") or {}).get("children"):
                    break
            if not isinstance(data, dict):
                continue
            children = (data.get("data") or {}).get("children", []) or []
            for child in children:
                row = child.get("data", {}) if isinstance(child, dict) else {}
                if not isinstance(row, dict):
                    continue
                title = clean_html(row.get("title", ""), 300)
                if not title:
                    continue
                dt = parse_datetime(row.get("created_utc"))
                items.append(
                    NewsItem(
                        id=stable_id("reddit", row.get("id") or title),
                        title=title,
                        url=f"https://www.reddit.com{row.get('permalink', '')}",
                        summary=clean_html(row.get("selftext", ""), 600),
                        author=str(row.get("author", "")),
                        published_at=iso(dt),
                        extra={
                            "subreddit": row.get("subreddit", sub),
                            "score": row.get("score", 0),
                            "num_comments": row.get("num_comments", 0),
                        },
                    )
                )
        return items
