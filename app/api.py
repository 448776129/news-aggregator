"""FastAPI 查询接口：GET /api/news?date=YYYY-MM-DD&category=finance。"""
from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from . import query, storage
from .web import home_html

app = FastAPI(title="新闻聚合查询接口", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def home():
    return home_html()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/dates")
def dates():
    return {"dates": query.list_dates()}


@app.get("/api/categories")
def categories(date: str | None = None):
    target = query.resolve_date(date)
    return {"date": target, "categories": query.list_categories(target)}


@app.get("/api/sources")
def sources(date: str | None = None):
    target = query.resolve_date(date)
    result: dict[str, dict] = {}
    for category in query.list_categories(target):
        payload = query.load_payload(target, category)
        if not payload:
            continue
        for row in payload.get("sources", []) or []:
            if isinstance(row, dict) and row.get("name"):
                result[row["name"]] = row
    return {"date": target, "sources": sorted(result.values(), key=lambda x: x.get("name", ""))}


@app.get("/api/news")
def news(
    date: str | None = Query(default=None, description="YYYY-MM-DD，默认最新一天"),
    category: str | None = Query(default=None, description="finance / english / community / stocktwits / reddit，默认全部"),
    source: str | None = Query(default=None, description="数据源代码，如 cls、reddit"),
    keyword: str | None = Query(default=None, description="标题或摘要关键词"),
    limit: int | None = Query(default=None, ge=1, le=1000, description="返回条数上限"),
):
    return query.query_news(date=date, category=category, source=source, keyword=keyword, limit=limit)


@app.get("/api/news/{date}/{category}")
def news_by_path(date: str, category: str, limit: int | None = Query(default=None, ge=1, le=1000)):
    return query.query_news(date=date, category=category, limit=limit)


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
