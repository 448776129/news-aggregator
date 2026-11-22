"""采集流程编排：并发调用各源 -> 分类 -> 按天归档 -> 重建索引。"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from . import storage, translator
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

    # 归档日期以新闻站点发布的 published_date 为准；发布信息缺失时才回退到采集日。
    # 同一批抓取可能横跨多天，分别落到对应日期目录。
    buckets: dict[tuple[str, str], list] = {}
    for key, items in results.items():
        category = SOURCE_CATEGORY.get(key, "finance")
        for item in items:
            archive_date = item.published_date or date
            buckets.setdefault((archive_date, category), []).append(item)

    # 一个栏目只发一次翻译请求（跨日期的同类新闻合并翻译），避免逐批调用拖慢采集。
    category_items: dict[str, list] = {}
    for (_, category), bucket in buckets.items():
        category_items.setdefault(category, []).extend(bucket)

    translation_stats: dict[str, dict[str, Any]] = {}
    for category, items in category_items.items():
        # 复用各归档日已有的译文，避免每 5 分钟重复翻译相同条目。
        existing: dict[str, dict] = {}
        for (archive_date, cat) in buckets:
            if cat != category:
                continue
            previous = storage.load_day(archive_date, category) or {}
            for row in previous.get("items", []):
                if isinstance(row, dict) and row.get("id"):
                    existing[row["id"]] = row
        translation_stats[category] = translator.translate_items(items, existing)

    saved: dict[str, int] = {}
    saved_by_date: dict[str, int] = {}
    for (archive_date, category), bucket in sorted(buckets.items()):
        # 每个归档日单独统计来源条数，全局健康状态仍沿用本次采集结果。
        counts: dict[str, int] = {}
        for item in bucket:
            counts[item.source] = counts.get(item.source, 0) + 1
        source_results = [
            SourceResult(key, result.status, counts.get(key, 0), result.error)
            for key, result in statuses.items()
            if SOURCE_CATEGORY.get(key) == category
        ]
        payload = storage.save_day(archive_date, category, bucket, source_results)
        saved[category] = saved.get(category, 0) + payload["count"]
        saved_by_date[archive_date] = saved_by_date.get(archive_date, 0) + payload["count"]

    storage.rebuild_index()
    summary = {
        "date": date,
        "archive_dates": sorted(saved_by_date),
        "sources": {key: result.to_dict() for key, result in statuses.items()},
        "saved": saved,
        "saved_by_date": saved_by_date,
        "total": sum(saved.values()),
        "translation": translation_stats,
    }
    logger.info("抓取完成：%s", summary)
    return summary
