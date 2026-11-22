"""按小时翻译已归档新闻的标题与摘要。

- 只处理 TRANSLATE_DATE_FROM（默认 2026-11-22）及之后的日期目录
- 只翻译缺少 title_zh / summary_zh 的非中文条目，避免重复翻译
- 一个栏目一次 API 调用；跑不完就跳过，留给下一小时
- 只回写内容真正发生变化的文件，不产生空提交
"""
from __future__ import annotations

import json
import logging
import pathlib
import re
import sys
from collections import defaultdict
from typing import Any

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import storage, translator  # noqa: E402
from app.config import (  # noqa: E402
    DATA_DIR,
    TRANSLATE_API_KEY,
    TRANSLATE_DATE_FROM,
    TRANSLATE_ENABLED,
)
from app.models import NewsItem  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("newsagg.translate_archive")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_targets() -> dict[pathlib.Path, tuple[dict[str, Any], list[NewsItem]]]:
    root = pathlib.Path(DATA_DIR)
    targets: dict[pathlib.Path, tuple[dict[str, Any], list[NewsItem]]] = {}
    for path in sorted(root.glob("*/*.json")):
        archive_date = path.parent.name
        if not DATE_RE.fullmatch(archive_date) or archive_date < TRANSLATE_DATE_FROM:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        items = [
            NewsItem.from_dict(row)
            for row in payload.get("items", [])
            if isinstance(row, dict)
        ]
        targets[path] = (payload, items)
    return targets


def main() -> int:
    if not TRANSLATE_ENABLED:
        print("TRANSLATE_ENABLED=0，跳过翻译")
        return 0
    if not TRANSLATE_API_KEY:
        print("未配置 TRANSLATE_API_KEY，跳过翻译")
        return 0

    targets = load_targets()
    if not targets:
        print(f"没有 {TRANSLATE_DATE_FROM} 及之后的归档数据")
        return 0

    by_category: dict[str, list[NewsItem]] = defaultdict(list)
    for (payload, items) in targets.values():
        for item in items:
            by_category[item.category or item.crawl_date].append(item)

    stats: dict[str, dict[str, Any]] = {}
    for category in sorted(by_category):
        stats[category] = translator.translate_items(by_category[category])

    changed_files = 0
    for path, (payload, items) in targets.items():
        new_items = [item.to_dict() for item in items]
        if new_items == payload.get("items"):
            continue
        payload["items"] = new_items
        payload["count"] = len(new_items)
        storage._write_json(str(path), payload)
        changed_files += 1

    if changed_files:
        storage.rebuild_index()

    summary = {
        "date_from": TRANSLATE_DATE_FROM,
        "files_scanned": len(targets),
        "files_changed": changed_files,
        "categories": stats,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
