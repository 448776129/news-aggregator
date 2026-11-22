"""全局配置：分类、数据源注册表、运行参数。

所有参数均可通过环境变量覆盖，便于在 GitHub Actions Secrets 中配置。
"""
from __future__ import annotations

import json
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

# 自动加载项目根目录的 .env（本地开发用；GitHub Actions 使用 Secrets 环境变量）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# 分类：代码 -> 中文名。查询接口统一使用分类代码。
CATEGORIES: dict[str, str] = {
    "finance": "财经新闻",
    "english": "英文新闻",
    "community": "社区新闻",
}

# 数据源 -> 分类。用户可通过 NEWS_SOURCE_CATEGORY_MAP 覆盖。
SOURCE_CATEGORY: dict[str, str] = {
    "yahoo": "english",       # 雅虎新闻 / Yahoo Finance
    "sina": "finance",        # 新浪财经
    "jin10": "finance",       # 金十数据
    "cls": "finance",         # 财联社
    "xueqiu": "community",    # 雪球
    "stocktwits": "community",  # Stocktwits
    "reddit": "community",    # Reddit
    "tradingview": "english",  # TradingView
    "alpaca": "english",      # Alpaca News
    "msn": "english",         # 微软 MSN / Bing News
}

# 数据源 -> 展示名与语言
SOURCE_META: dict[str, dict[str, str]] = {
    "yahoo": {"name": "雅虎新闻", "lang": "en"},
    "sina": {"name": "新浪财经", "lang": "zh"},
    "jin10": {"name": "金十数据", "lang": "zh"},
    "cls": {"name": "财联社", "lang": "zh"},
    "xueqiu": {"name": "雪球", "lang": "zh"},
    "stocktwits": {"name": "Stocktwits", "lang": "en"},
    "reddit": {"name": "Reddit", "lang": "en"},
    "tradingview": {"name": "TradingView", "lang": "en"},
    "alpaca": {"name": "Alpaca News", "lang": "en"},
    "msn": {"name": "微软 MSN", "lang": "en"},
}


def _load_category_override() -> None:
    raw = os.getenv("NEWS_SOURCE_CATEGORY_MAP", "").strip()
    if not raw:
        return
    try:
        override = json.loads(raw)
        if isinstance(override, dict):
            for key, value in override.items():
                if key in SOURCE_CATEGORY and value in CATEGORIES:
                    SOURCE_CATEGORY[key] = value
    except json.JSONDecodeError:
        pass


_load_category_override()


def get_timezone() -> ZoneInfo:
    name = os.getenv("NEWS_TIMEZONE", "Asia/Shanghai").strip() or "Asia/Shanghai"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Shanghai")


TZ = get_timezone()

MAX_ITEMS = int(os.getenv("NEWS_MAX_ITEMS", "50") or 50)
WORKERS = max(1, int(os.getenv("NEWS_WORKERS", "4") or 4))

JIN10_SECRET_KEY = os.getenv("JIN10_SECRET_KEY", "").strip()
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "").strip()
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "").strip()
ALPACA_DATA_URL = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets").strip().rstrip("/")
XUEQIU_COOKIE = os.getenv("XUEQIU_COOKIE", "").strip()

GITHUB_RAW_BASE_URL = os.getenv("GITHUB_RAW_BASE_URL", "").strip().rstrip("/")
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

# 标题/摘要翻译（OpenAI 兼容 Chat Completions 接口）
TRANSLATE_ENABLED = os.getenv("TRANSLATE_ENABLED", "1").strip().lower() not in ("0", "false", "no", "off")
TRANSLATE_API_KEY = os.getenv("TRANSLATE_API_KEY", "").strip()
TRANSLATE_BASE_URL = os.getenv(
    "TRANSLATE_BASE_URL", "https://token.sensenova.cn/v1"
).strip().rstrip("/")
# 额度耗尽 / 限流时按顺序切换下一个模型
TRANSLATE_MODELS = [
    m.strip() for m in os.getenv(
        "TRANSLATE_MODELS",
        "sensenova-6.8-flash-lite",
    ).split(",") if m.strip()
]
# 翻译总时间预算（秒）；超时就跳过剩余翻译，保证采集任务按时结束。
TRANSLATE_TIME_BUDGET = max(5, int(os.getenv("TRANSLATE_TIME_BUDGET", "90") or 90))
# 一个栏目一次 API 调用完成翻译；批大小与单次上限都放到足够大。
TRANSLATE_BATCH_SIZE = max(1, int(os.getenv("TRANSLATE_BATCH_SIZE", "1000") or 1000))
# 单次运行最多翻译多少条；0 表示不限制。
TRANSLATE_MAX_ITEMS = max(0, int(os.getenv("TRANSLATE_MAX_ITEMS", "0") or 0))
TRANSLATE_TARGET_LANG = os.getenv("TRANSLATE_TARGET_LANG", "简体中文").strip() or "简体中文"

# 数据目录：默认项目根目录下的 data/，可通过 NEWS_DATA_DIR 覆盖
DATA_DIR = os.getenv("NEWS_DATA_DIR", "").strip() or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)

# 各源默认订阅对象，可通过环境变量覆盖（逗号分隔）
YAHOO_SYMBOLS = [s for s in os.getenv("NEWS_YAHOO_SYMBOLS", "AAPL,MSFT,NVDA,TSLA,^GSPC").split(",") if s]
STOCKTWITS_SYMBOLS = [s for s in os.getenv("NEWS_STOCKTWITS_SYMBOLS", "AAPL,TSLA,NVDA,SPY").split(",") if s]
REDDIT_SUBS = [s for s in os.getenv("NEWS_REDDIT_SUBS", "stocks,wallstreetbets,investing").split(",") if s]
TRADINGVIEW_SYMBOLS = [
    s for s in os.getenv("NEWS_TRADINGVIEW_SYMBOLS", "NASDAQ:AAPL,NASDAQ:NVDA,NASDAQ:TSLA").split(",") if s
]
BING_QUERIES = [s for s in os.getenv("NEWS_BING_QUERIES", "stock market,economy,earnings").split(",") if s]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
