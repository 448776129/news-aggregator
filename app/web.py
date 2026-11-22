"""首页：展示最新新闻、分类入口与 API 用法。"""
from __future__ import annotations

import html
from typing import Any

from . import query
from .config import CATEGORIES

_CATEGORY_LABEL = {
    "finance": "财经新闻",
    "english": "英文新闻",
    "community": "社区新闻",
}


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _load_latest() -> tuple[str, dict[str, list[dict[str, Any]]], dict[str, Any]]:
    dates = query.list_dates()
    if not dates:
        return "", {}, {}
    date = dates[0]
    categories = query.list_categories(date)
    buckets: dict[str, list[dict[str, Any]]] = {}
    index = query._remote_index() or {}
    for category in categories:
        payload = query.load_payload(date, category)
        if payload:
            buckets[category] = payload.get("items", []) or []
    return date, buckets, index


def home_html() -> str:
    date, buckets, index = _load_latest()

    total = sum(len(items) for items in buckets.values())
    cards = []
    for key, label in _CATEGORY_LABEL.items():
        count = len(buckets.get(key, []))
        cards.append(
            f'<a class="card" href="/api/news?date={_esc(date)}&category={key}">'
            f'<span class="card-label">{_esc(label)}</span>'
            f'<span class="card-count">{count}</span>'
            f'<span class="card-sub">查看 JSON →</span></a>'
        )

    rows = []
    for category, items in buckets.items():
        for item in items[:8]:
            title = item.get("title_zh") or item.get("title") or "(无标题)"
            url = item.get("url") or ""
            source = item.get("source_name") or item.get("source") or ""
            published = item.get("published_at") or item.get("published_date") or ""
            link = (
                f'<a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(title)}</a>'
                if url else _esc(title)
            )
            rows.append(
                '<tr>'
                f'<td><span class="tag">{_esc(_CATEGORY_LABEL.get(category, category))}</span></td>'
                f'<td class="title">{link}</td>'
                f'<td class="source">{_esc(source)}</td>'
                f'<td class="time">{_esc(published[:16])}</td>'
                '</tr>'
            )
    # 按分类顺序展示，最多 18 条
    rows = rows[:18]

    dates_html = "".join(f"<code>{_esc(d)}</code> " for d in query.list_dates()[:12])

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>新闻聚合 API</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
         background:#f7f9fc; color:#1f2937; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:40px 20px 64px; }}
  h1 {{ font-size:30px; margin:0 0 8px; color:#111827; }}
  .sub {{ color:#6b7280; margin:0 0 28px; line-height:1.7; }}
  .badge {{ display:inline-block; background:#e0edff; color:#1d4ed8; padding:3px 10px; border-radius:999px; font-size:12px; margin-right:8px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:14px; margin-bottom:32px; }}
  .card {{ display:block; background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:18px;
           text-decoration:none; color:inherit; box-shadow:0 1px 2px rgba(0,0,0,.03); transition:.15s; }}
  .card:hover {{ border-color:#93c5fd; transform:translateY(-2px); }}
  .card-label {{ display:block; font-size:14px; color:#6b7280; }}
  .card-count {{ display:block; font-size:32px; font-weight:700; color:#2563eb; margin:6px 0; }}
  .card-sub {{ font-size:12px; color:#9ca3af; }}
  h2 {{ font-size:18px; margin:32px 0 12px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid #e5e7eb; border-radius:12px; overflow:hidden; }}
  th,td {{ text-align:left; padding:11px 14px; border-bottom:1px solid #f0f2f5; font-size:14px; }}
  th {{ background:#f9fafb; color:#6b7280; font-weight:600; }}
  tr:last-child td {{ border-bottom:0; }}
  td.title a {{ color:#1f2937; text-decoration:none; }}
  td.title a:hover {{ color:#2563eb; }}
  td.source,td.time {{ color:#9ca3af; white-space:nowrap; }}
  .tag {{ background:#f3f4f6; color:#4b5563; padding:2px 8px; border-radius:6px; font-size:12px; }}
  code {{ background:#eef2ff; color:#3730a3; padding:2px 7px; border-radius:5px; font-size:12px; }}
  pre {{ background:#111827; color:#e5e7eb; padding:16px; border-radius:10px; overflow:auto; font-size:13px; }}
  .footer {{ margin-top:36px; color:#9ca3af; font-size:12px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>新闻聚合 API 🦞</h1>
  <p class="sub">
    <span class="badge">每 5 分钟采集</span>
    <span class="badge">按发布时间归档</span>
    <span class="badge">多源聚合</span>
    最新归档日期 <strong>{_esc(date) or '暂无'}</strong>，当前共 <strong>{total}</strong> 条新闻。
  </p>

  <div class="cards">{''.join(cards)}</div>

  <h2>最新新闻</h2>
  <table>
    <thead><tr><th>分类</th><th>标题</th><th>来源</th><th>发布时间</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="4">暂无数据</td></tr>'}</tbody>
  </table>

  <h2>接口用法</h2>
  <pre>GET /health
GET /api/dates
GET /api/categories?date={_esc(date)}
GET /api/sources?date={_esc(date)}
GET /api/news?date={_esc(date)}&category=finance&limit=20
GET /api/news?date={_esc(date)}&category=english&keyword=rate

数据文件：https://raw.githubusercontent.com/448776129/news-aggregator/main/data/index.json</pre>

  <h2>已归档日期</h2>
  <p>{dates_html or '暂无'}</p>

  <div class="footer">数据源：金十 · 新浪 · 雅虎 · Alpaca · Finnhub · TradingView · Stocktwits · MSN · 雪球 · Reddit · 财联社</div>
</div>
</body>
</html>"""
