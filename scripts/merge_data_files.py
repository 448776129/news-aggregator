"""把一侧 data/ 目录按 id 合并进另一侧，用于并发推送被拒后的冲突化解。

场景：两个采集 run 同时改同一批 JSON，rebase 必然冲突。做法是把自己这轮
改动留在临时目录，reset 到远端最新，再用本脚本按 id 合并回来，最后重新提交。

用法：
    python scripts/merge_data_files.py <源 data 目录> <目标 data 目录>
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage import merge_items, rebuild_index  # noqa: E402


def merge_file(src_path: str, dst_path: str) -> int:
    with open(src_path, encoding="utf-8") as fh:
        src = json.load(fh)
    src_items = src.get("items", []) if isinstance(src, dict) else src
    if not isinstance(src_items, list):
        return 0

    dst: dict = {}
    if os.path.exists(dst_path):
        try:
            with open(dst_path, encoding="utf-8") as fh:
                dst = json.load(fh)
        except (OSError, json.JSONDecodeError):
            dst = {}
    dst_items = dst.get("items", []) if isinstance(dst, dict) else []

    before = len(dst_items)
    merged = merge_items(dst_items, src_items)
    added = len(merged) - before
    if added <= 0 and os.path.exists(dst_path):
        return 0

    payload = dict(dst) if isinstance(dst, dict) else {}
    payload["items"] = merged

    # 合并 sources 统计：同源取较新的结果
    src_sources = src.get("sources") if isinstance(src, dict) else None
    if src_sources:
        cur = {s.get("name"): s for s in payload.get("sources", []) if isinstance(s, dict)}
        for s in src_sources:
            if not isinstance(s, dict):
                continue
            old = cur.get(s.get("name"))
            if old is None or (s.get("fetched_at") or "") >= (old.get("fetched_at") or ""):
                cur[s.get("name")] = s
        payload["sources"] = list(cur.values())

    if isinstance(src, dict):
        for key in ("date", "category", "updated_at", "generated_at"):
            if src.get(key) and not payload.get(key):
                payload[key] = src[key]

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return added


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src_dir, dst_dir = sys.argv[1], sys.argv[2]
    total_added = 0
    files = 0
    for src_path in sorted(glob.glob(os.path.join(src_dir, "*", "*.json"))):
        rel = os.path.relpath(src_path, src_dir)
        dst_path = os.path.join(dst_dir, rel)
        added = merge_file(src_path, dst_path)
        files += 1
        total_added += added
        if added:
            print(f"  {rel}: +{added}")
    rebuild_index()
    print(f"合并完成：{files} 个文件，新增 {total_added} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
