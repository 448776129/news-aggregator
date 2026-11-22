#!/usr/bin/env python3
"""news-aggregator 命令行入口。

示例：
  python run.py fetch
  python run.py fetch --date 2026-11-22 --source sina,cls
  python run.py query --date 2026-11-22 --category finance --limit 20
  python run.py dates
  python run.py serve --port 8000
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from app import pipeline, query, storage
from app.collectors import REGISTRY, SOURCE_CATEGORY
from app.config import CATEGORIES, DATA_DIR


def dump(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="多源新闻按天归档与查询工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="抓取并归档")
    p_fetch.add_argument("--date", help="归档日期 YYYY-MM-DD，默认今天")
    p_fetch.add_argument("--source", help="只抓取指定源，逗号分隔，如 sina,cls")
    p_fetch.add_argument("--category", help="只抓取指定分类，逗号分隔")

    p_query = sub.add_parser("query", help="查询新闻")
    p_query.add_argument("--date", help="YYYY-MM-DD 或 latest，默认 latest")
    p_query.add_argument("--category", choices=list(CATEGORIES), help="分类，默认全部")
    p_query.add_argument("--source", help="数据源代码")
    p_query.add_argument("--keyword", help="关键词过滤")
    p_query.add_argument("--limit", type=int, help="返回条数上限")
    p_query.add_argument("--raw", action="store_true", help="只输出 items 数组")

    sub.add_parser("dates", help="列出已归档日期")
    p_cats = sub.add_parser("categories", help="列出分类")
    p_cats.add_argument("--date")
    p_src = sub.add_parser("sources", help="列出某天各源采集状态")
    p_src.add_argument("--date")

    p_serve = sub.add_parser("serve", help="启动 HTTP 查询接口")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("config", help="查看当前配置与数据源映射")
    sub.add_parser("doctor", help="逐个测试数据源连通性（不写文件）")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)

    if args.command == "fetch":
        sources = [s.strip() for s in args.source.split(",")] if getattr(args, "source", None) else None
        categories = [c.strip() for c in args.category.split(",")] if getattr(args, "category", None) else None
        dump(pipeline.run_fetch(date=args.date, sources=sources, categories=categories))

    elif args.command == "query":
        result = query.query_news(
            date=args.date,
            category=args.category,
            source=args.source,
            keyword=args.keyword,
            limit=args.limit,
        )
        dump(result["items"] if args.raw else result)

    elif args.command == "dates":
        dump({"dates": query.list_dates()})

    elif args.command == "categories":
        dump({"categories": query.list_categories(args.date)})

    elif args.command == "sources":
        from app.api import sources as sources_api

        dump(sources_api(args.date))

    elif args.command == "serve":
        from app.api import run_server

        run_server(args.host, args.port)

    elif args.command == "config":
        dump(
            {
                "categories": CATEGORIES,
                "source_category": SOURCE_CATEGORY,
                "registry": sorted(REGISTRY),
                "data_dir": DATA_DIR,
            }
        )

    elif args.command == "doctor":
        from app.utils import today_str

        report = {}
        for key, cls in REGISTRY.items():
            collector = cls()
            if not getattr(collector, "available", True):
                report[key] = {"status": "skipped", "reason": "未配置凭证"}
                continue
            try:
                items = collector.run(today_str())
                report[key] = {"status": "ok" if items else "empty", "count": len(items)}
            except Exception as exc:
                report[key] = {"status": "error", "error": str(exc)[:160]}
        dump(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
