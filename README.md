# 多源新闻自动化归档与查询

从雅虎新闻、新浪财经、金十数据、财联社、雪球、Stocktwits、Reddit、TradingView、Alpaca News、微软 MSN 抓取资讯，按 **财经新闻 / 英文新闻 / 社区新闻** 分类，以 **天** 为单位归档为 JSON，并通过 GitHub Actions 定时自动提交。提供命令行、Python 与 HTTP API 三种查询方式，可按 **日期 + 分类** 精确取数。

## 数据源与分类

| 数据源 | 分类代码 | 分类 | 抓取方式 | 凭证 |
| --- | --- | --- | --- | --- |
| 雅虎新闻 / Yahoo Finance | `english` | 英文新闻 | RSS | 无 |
| 新浪财经 | `finance` | 财经新闻 | 滚动新闻 API + RSS 兜底 | 无 |
| 金十数据 | `finance` | 财经新闻 | 开放平台 API / 公开快讯脚本 | 可选 |
| 财联社 | `finance` | 财经新闻 | 电报 nodeapi | 无 |
| 雪球 | `community` | 社区新闻 | 热帖 JSON（匿名 Cookie） | 可选 |
| Stocktwits | `community` | 社区新闻 | 个股消息流 JSON | 无 |
| Reddit | `community` | 社区新闻 | `.json` 公开接口 | 无 |
| TradingView | `english` | 英文新闻 | 头条 JSON | 无 |
| Alpaca News | `english` | 英文新闻 | `v1beta1/news` | 需要 |
| 微软 MSN | `english` | 英文新闻 | Bing News RSS（微软新闻源） | 无 |

分类映射可在 `.env` 中用 `NEWS_SOURCE_CATEGORY_MAP` 覆盖，例如：

```bash
NEWS_SOURCE_CATEGORY_MAP={"reddit":"english","xueqiu":"finance"}
```

> 说明：MSN 没有稳定的公开 RSS，使用 Bing News RSS 作为等价入口；金十开放平台与 Alpaca 需要申请密钥，未配置时会自动降级或跳过，不影响其他源。

## 目录结构

```
news-aggregator/
├── app/
│   ├── config.py          # 分类与数据源配置（环境变量覆盖）
│   ├── models.py          # 统一数据结构
│   ├── collectors/        # 各数据源采集器
│   ├── storage.py         # 按天/分类落盘与索引
│   ├── pipeline.py        # 抓取编排
│   ├── query.py           # 查询逻辑（本地 + 远端回退）
│   └── api.py             # FastAPI 接口
├── .github/workflows/daily-news.yml
├── data/                  # 归档数据（自动生成）
│   ├── index.json
│   └── 2026-11-22/
│       ├── finance.json
│       ├── english.json
│       └── community.json
├── run.py                 # CLI 入口
└── requirements.txt
```

## 本地使用

```bash
cd news-aggregator
pip install -r requirements.txt
cp .env.example .env        # 按需填写密钥，程序会自动加载项目根目录的 .env

# 抓取当天全部数据源
python run.py fetch

# 抓取指定日期 / 指定源 / 指定分类
python run.py fetch --date 2026-11-22 --source sina,cls --category finance

# 查询
python run.py query --date 2026-11-22 --category finance --limit 20
python run.py query --date latest --category community --source reddit --keyword AAPL
python run.py dates
python run.py categories --date 2026-11-22
python run.py sources --date 2026-11-22
python run.py doctor        # 逐源连通性自检
```

## HTTP API

```bash
python run.py serve --port 8000
```

| 接口 | 说明 |
| --- | --- |
| `GET /api/news?date=2026-11-22&category=finance` | 按日期 + 分类查询 |
| `GET /api/news?date=latest&source=cls&keyword=央行&limit=20` | 按来源、关键词过滤 |
| `GET /api/news/2026-11-22/english` | 路径式快捷查询 |
| `GET /api/dates` | 已归档日期列表 |
| `GET /api/categories?date=2026-11-22` | 某天可用分类 |
| `GET /api/sources?date=2026-11-22` | 各源采集状态 |
| `GET /health` | 健康检查 |

Python 直接调用：

```python
from app.query import query_news

result = query_news(date="2026-11-22", category="finance", limit=10)
for item in result["items"]:
    print(item["title"], item["url"], item["published_at"])
```

远端查询（本地无数据时回退到 GitHub）：设置 `GITHUB_RAW_BASE_URL=https://raw.githubusercontent.com/<owner>/<repo>/main`；私有仓库可改用 `GITHUB_REPO` + `GITHUB_TOKEN`。

## 数据格式

`data/2026-11-22/finance.json`：

```json
{
  "date": "2026-11-22",
  "category": "finance",
  "category_name": "财经新闻",
  "timezone": "Asia/Shanghai",
  "generated_at": "2026-11-22T12:00:00+08:00",
  "count": 120,
  "sources": [{"name": "cls", "status": "ok", "count": 60, "error": ""}],
  "items": [
    {
      "id": "cls:123456",
      "title": "...",
      "url": "https://www.cls.cn/detail/123456",
      "source": "cls",
      "source_name": "财联社",
      "summary": "...",
      "published_at": "2026-11-22T10:12:00+08:00",
      "published_date": "2026-11-22",
      "fetched_at": "2026-11-22T11:00:00+08:00",
      "crawl_date": "2026-11-22",
      "lang": "zh",
      "category": "finance",
      "extra": {}
    }
  ]
}
```

**日期语义**：目录按 `crawl_date`（抓取归档日）划分；每条新闻同时保留 `published_at` / `published_date`（真实发布时间）。同一天多次运行会在原文件上按 `id` 去重合并，不会覆盖。

## GitHub Actions

1. 把项目推送到 GitHub 仓库。
2. 在 **Settings → Secrets and variables → Actions** 添加需要的密钥：`JIN10_SECRET_KEY`、`ALPACA_API_KEY`、`ALPACA_SECRET_KEY`、`XUEQIU_COOKIE`（均为可选）。
3. Workflow 默认每 6 小时执行一次（北京时间 02:00 / 08:00 / 14:00 / 20:00），也可在 Actions 页面手动触发并指定日期回填。
4. 仓库需允许 Actions 写入：`Settings → Actions → General → Workflow permissions` 选择 **Read and write permissions**。

## 可调参数

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `NEWS_TIMEZONE` | `Asia/Shanghai` | 按天归档时区 |
| `NEWS_MAX_ITEMS` | `50` | 每个源最多保留条数 |
| `NEWS_WORKERS` | `4` | 并发采集线程数 |
| `NEWS_YAHOO_SYMBOLS` | `AAPL,MSFT,NVDA,TSLA,^GSPC` | 雅虎订阅代码 |
| `NEWS_STOCKTWITS_SYMBOLS` | `AAPL,TSLA,NVDA,SPY` | Stocktwits 订阅代码 |
| `NEWS_REDDIT_SUBS` | `stocks,wallstreetbets,investing` | Reddit 板块 |
| `NEWS_TRADINGVIEW_SYMBOLS` | `NASDAQ:AAPL,NASDAQ:NVDA,NASDAQ:TSLA` | TradingView 订阅代码 |
| `NEWS_BING_QUERIES` | `stock market,economy,earnings` | MSN/Bing 查询词 |

## 注意事项

- 各站点的公开接口可能调整或限流；单个源失败会记录到 `sources[].status`，不影响其他源与整体归档。
- 仅供个人研究与内部信息聚合使用，请遵守各平台服务条款与版权要求。
