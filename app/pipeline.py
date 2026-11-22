"""采集流程编排：并发调用各源 -> 分类 -> 按天归档 -> 重建索引。"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from . import storage
from .collectors import SOURCE_CATEGORY, all_collectors, get_collector
from .config import WORKERS
from .models import SourceResult
from .utils import today_str

logger = logging.getLogger("newsagg.pipeline")


def run_fetch(
    date: str | None = None,
    sources: list[str] | None = None,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    date = date or today_str()
    selected = [get_collector(name) for name in sources] if sources else all_collectors()
    selected = [c for c in selected if c is not None]
    if categories:
        selected = [c for c in selected if SOURCE_CATEGORY.get(c.key) in categories]

    results: dict[str, list] = {}
    statuses: dict[str, SourceResult] = {}
    futures: dict[Any, str] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for collector in selected:
            if not getattr(collector, "available", True):
                statuses[collector.key] = SourceResult(collector.key, "skipped", 0, "未配置所需凭证")
                continue
            future = pool.submit(collector.run, date)
            futures[future] = collector.key

        for future in as_completed(futures):
            key = futures[future]
            try:
                items = future.result() or []
                results[key] = items
                statuses[key] = SourceResult(key, "ok", len(items))
            except Exception as exc:  # 兜底，采集器内部通常已捕获
                logger.exception("采集器 %s 失败", key)
                statuses[key] = SourceResult(key, "error", 0, str(exc)[:200])

    saved: dict[str, int] = {}
    for category in sorted({SOURCE_CATEGORY.get(key, "finance") for key in results}):
        bucket = [item for key, items in results.items() if SOURCE_CATEGORY.get(key) == category for item in items]
        source_results = [result for key, result in statuses.items() if SOURCE_CATEGORY.get(key) == category]
        payload = storage.save_day(date, category, bucket, source_results)
        saved[category] = payload["count"]

    storage.rebuild_index()
    summary = {
        "date": date,
        "sources": {key: result.to_dict() for key, result in statuses.items()},
        "saved": saved,
        "total": sum(saved.values()),
    }
    logger.info("抓取完成：%s", summary)
    return summary
