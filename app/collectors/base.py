"""采集器基类：统一补齐元数据、去重与条数限制。"""
from __future__ import annotations

from ..config import MAX_ITEMS, SOURCE_CATEGORY, SOURCE_META
from ..models import NewsItem
from ..utils import iso, local_now, parse_datetime, day


class BaseCollector:
    key: str = ""

    def collect(self, date: str) -> list[NewsItem]:  # pragma: no cover - 由子类实现
        raise NotImplementedError

    def run(self, date: str) -> list[NewsItem]:
        try:
            raw = self.collect(date) or []
        except Exception:  # 单个源异常不影响整体
            import logging

            logging.getLogger("newsagg").exception("采集器 %s 异常", self.key)
            return []
        meta = SOURCE_META.get(self.key, {"name": self.key, "lang": "zh"})
        seen: set[str] = set()
        result: list[NewsItem] = []
        fetched_at = iso(local_now())
        for item in raw:
            if not item or not item.title or item.id in seen:
                continue
            seen.add(item.id)
            item.source = item.source or self.key
            item.source_name = item.source_name or meta["name"]
            item.category = item.category or SOURCE_CATEGORY.get(self.key, "finance")
            item.lang = meta["lang"]
            item.crawl_date = date
            item.fetched_at = item.fetched_at or fetched_at
            if not item.published_date:
                item.published_date = day(parse_datetime(item.published_at)) or date
            result.append(item)
            if len(result) >= MAX_ITEMS:
                break
        return result
