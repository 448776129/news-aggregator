"""Reddit：优先官方公开 .json 接口，被 403 拦截时回退到 Arctic Shift 公开镜像。

官方接口对数据中心 IP 常返回 403，因此增加镜像回退；两者返回的帖子结构兼容
（id / title / selftext / permalink / author / created_utc / score / num_comments）。
"""
from __future__ import annotations

from typing import Any

from ..config import REDDIT_SUBS
from ..http_client import get_json
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, stable_id
from .base import BaseCollector

MIRROR = "https://arctic-shift.photon-reddit.com/api/posts/search"


class RedditCollector(BaseCollector):
    key = "reddit"
    HEADERS = {"User-Agent": "news-aggregator/1.0 (by /u/open-source)", "Accept": "application/json"}

    def _fetch_official(self, sub: str) -> list[dict[str, Any]]:
        for base in ("https://www.reddit.com", "https://old.reddit.com"):
            data = get_json(
                f"{base}/r/{sub}/new.json",
                params={"limit": 50, "raw_json": 1},
                headers=self.HEADERS,
                timeout=6,
            )
            if isinstance(data, dict):
                children = (data.get("data") or {}).get("children") or []
                if children:
                    return [c.get("data", {}) for c in children if isinstance(c, dict)]
        return []

    def _fetch_mirror(self, sub: str) -> list[dict[str, Any]]:
        data = get_json(
            MIRROR,
            params={"subreddit": sub, "limit": 50, "sort": "desc"},
            headers={"Accept": "application/json"},
            timeout=12,
        )
        rows = data.get("data") if isinstance(data, dict) else None
        return [r for r in rows or [] if isinstance(r, dict)]

    def collect(self, date: str) -> list[NewsItem]:
        per_sub: list[list[NewsItem]] = []
        official_usable = True  # 首个 subreddit 判定被墙后，本轮不再试官方接口，避免浪费时间
        for sub in REDDIT_SUBS:
            rows = self._fetch_official(sub) if official_usable else []
            if not rows:
                official_usable = False
                rows = self._fetch_mirror(sub)
            batch: list[NewsItem] = []
            for row in rows:
                if row.get("stickied") or row.get("over_18"):
                    continue
                title = clean_html(row.get("title", ""), 300)
                if not title:
                    continue
                permalink = row.get("permalink") or ""
                if permalink.startswith("/"):
                    permalink = f"https://www.reddit.com{permalink}"
                dt = parse_datetime(row.get("created_utc"))
                batch.append(
                    NewsItem(
                        id=stable_id("reddit", row.get("id") or title),
                        title=title,
                        url=permalink,
                        summary=clean_html(row.get("selftext", "")),
                        author=str(row.get("author", "")),
                        published_at=iso(dt),
                        extra={
                            "subreddit": row.get("subreddit", sub),
                            "score": row.get("score", 0),
                            "num_comments": row.get("num_comments", 0),
                        },
                    )
                )
            batch.sort(key=lambda i: i.published_at or "", reverse=True)
            per_sub.append(batch)

        # 多个 subreddit 轮转交错，基类按 MAX_ITEMS 截断时各板块都有名额，
        # 不会被 wallstreetbets 这种高活跃板块完全挤掉。
        items: list[NewsItem] = []
        for idx in range(max((len(b) for b in per_sub), default=0)):
            for batch in per_sub:
                if idx < len(batch):
                    items.append(batch[idx])
        return items
