"""数据源采集器注册表。"""
from __future__ import annotations

from ..config import CATEGORIES, SOURCE_CATEGORY, SOURCE_META
from .base import BaseCollector
from .alpaca import AlpacaCollector
from .cls import ClsCollector
from .jin10 import Jin10Collector
from .msn import MsnCollector
from .reddit import RedditCollector
from .sina import SinaCollector
from .stocktwits import StocktwitsCollector
from .tradingview import TradingViewCollector
from .xueqiu import XueqiuCollector
from .yahoo import YahooCollector

REGISTRY: dict[str, type[BaseCollector]] = {
    "yahoo": YahooCollector,
    "sina": SinaCollector,
    "jin10": Jin10Collector,
    "cls": ClsCollector,
    "xueqiu": XueqiuCollector,
    "stocktwits": StocktwitsCollector,
    "reddit": RedditCollector,
    "tradingview": TradingViewCollector,
    "alpaca": AlpacaCollector,
    "msn": MsnCollector,
}


def all_collectors() -> list[BaseCollector]:
    return [cls() for cls in REGISTRY.values()]


def get_collector(name: str) -> BaseCollector | None:
    cls = REGISTRY.get(name)
    return cls() if cls else None


__all__ = [
    "CATEGORIES",
    "SOURCE_CATEGORY",
    "SOURCE_META",
    "REGISTRY",
    "BaseCollector",
    "all_collectors",
    "get_collector",
]
