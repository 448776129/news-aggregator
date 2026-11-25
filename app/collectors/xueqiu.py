"""雪球：需登录态 Cookie（匿名 token 会被 WAF 拦截），抓取热门/最新帖子。"""
from __future__ import annotations

import logging

import requests

from ..config import USER_AGENT, XUEQIU_COOKIE
from ..http_client import get_json
from ..models import NewsItem
from ..utils import clean_html, iso, parse_datetime, pick, stable_id
from .base import BaseCollector

logger = logging.getLogger("newsagg.xueqiu")


class XueqiuCollector(BaseCollector):
    key = "xueqiu"

    ENDPOINTS = (
        "https://xueqiu.com/statuses/hot/list.json",
        "https://xueqiu.com/statuses/latest.json",
    )

    @property
    def available(self) -> bool:
        """雪球接口必须登录态 Cookie（匿名 token 会触发 WAF 或返回 10022 未登录）。"""
        return bool(XUEQIU_COOKIE)

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {"User-Agent": USER_AGENT, "Referer": "https://xueqiu.com/", "Accept": "application/json"}
        )
        if XUEQIU_COOKIE:
            session.headers["Cookie"] = XUEQIU_COOKIE
        else:
            try:
                session.get("https://xueqiu.com/", timeout=10)
            except requests.RequestException:
                pass
        return session

    def collect(self, date: str) -> list[NewsItem]:
        session = self._session()
        rows: list[dict] = []
        params = {"since_id": 0} if "hot" in self.ENDPOINTS[0] else {"count": 50, "page": 1}
        for url in self.ENDPOINTS:
            data = get_json(url, params=params, session=session)
            rows = list(self._iter_statuses(data))
            if rows:
                break
        if not rows:
            logger.warning("雪球未取到数据：Cookie 可能已过期或未配置（需要登录态 xq_a_token）")
        items: list[NewsItem] = []
        for row in rows:
            title = clean_html(pick(row, "title", "text", "description", default=""), 300)
            if not title:
                continue
            raw_id = pick(row, "id", "target", default=title)
            user = row.get("user") or {}
            author = user.get("screen_name", "") if isinstance(user, dict) else ""
            url = str(pick(row, "target", default="")) or f"https://xueqiu.com/statuses/show?id={raw_id}"
            dt = parse_datetime(pick(row, "created_at", "time", default=""))
            items.append(
                NewsItem(
                    id=stable_id("xueqiu", raw_id),
                    title=title,
                    url=url,
                    summary=clean_html(pick(row, "description", "text", default="")),
                    author=author,
                    published_at=iso(dt),
                )
            )
        return items

    @staticmethod
    def _iter_statuses(data, depth: int = 0):
        """兼容多种返回结构，递归找出看起来像帖子的字典。"""
        if depth > 4:
            return
        if isinstance(data, list):
            for value in data:
                yield from XueqiuCollector._iter_statuses(value, depth + 1)
        elif isinstance(data, dict):
            if any(k in data for k in ("id", "target")) and any(
                k in data for k in ("title", "text", "description")
            ):
                yield data
                return
            for value in data.values():
                if isinstance(value, (list, dict)):
                    yield from XueqiuCollector._iter_statuses(value, depth + 1)
