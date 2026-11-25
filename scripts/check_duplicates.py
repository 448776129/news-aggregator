"""归档数据去重体检：按 id 与（来源, URL）双维度扫描 data/ 下的 JSON。

用法：
    python scripts/check_duplicates.py            # 全量扫描
    python scripts/check_duplicates.py 2026-11-25 # 只扫指定日期

有重复时退出码为 1，便于在 CI 里做门禁。
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def normalize_url(url: str) -> str:
    """去掉查询串和锚点，仅用于跨 id 的辅助比对（不参与入库去重）。"""
    url = (url or "").strip()
    return url.split("#")[0].split("?")[0]


def scan(date_filter: str | None) -> dict:
    files = 0
    total = 0
    dup_ids: list[tuple[str, str, int]] = []
    dup_urls: list[tuple[str, str, int]] = []

    pattern = os.path.join(DATA_DIR, date_filter or "*", "*.json")
    for path in sorted(glob.glob(pattern)):
        if os.path.basename(path) in {"index.json"}:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        items = payload.get("items", []) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            continue
        files += 1
        total += len(items)

        id_counter = collections.Counter(i.get("id") for i in items if i.get("id"))
        for key, cnt in id_counter.items():
            if cnt > 1:
                dup_ids.append((path, key, cnt))

        seen: set[str] = set()
        url_counter: collections.Counter[str] = collections.Counter()
        for item in items:
            url = normalize_url(item.get("url", ""))
            if not url:
                continue
            key = f"{item.get('source')}|{url}"
            url_counter[key] += 1
            if key in seen:
                dup_urls.append((path, key, url_counter[key]))
            seen.add(key)

    return {
        "files": files,
        "items": total,
        "duplicate_ids": dup_ids,
        "duplicate_source_url": dup_urls,
    }


def main() -> int:
    date_filter = sys.argv[1] if len(sys.argv) > 1 else None
    report = scan(date_filter)
    scope = date_filter or "全部日期"
    print(f"扫描范围：{scope}")
    print(f"文件 {report['files']} 个，条目 {report['items']} 条")
    print(f"重复 id：{len(report['duplicate_ids'])} 组")

    for path, key, cnt in report["duplicate_ids"][:10]:
        print(f"  [重复 id] {os.path.relpath(path, os.path.dirname(DATA_DIR))} {key} ×{cnt}")

    # 同 URL 不同 id：多数是源自带的页面地址不唯一（如 stocktwits 的 /symbol/XXX），
    # 仅作提示，不判定为重复入库。
    groups = {(path, key) for path, key, _ in report["duplicate_source_url"]}
    by_source = collections.Counter(key.split("|")[0] for _, key in groups)
    if groups:
        top = "、".join(f"{k} {v}" for k, v in by_source.most_common(4))
        print(f"同源同 URL 但 id 不同（多为源地址不唯一，仅供参考）：{len(groups)} 组，主要来自 {top}")

    return 1 if report["duplicate_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
