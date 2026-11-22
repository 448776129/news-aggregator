"""统一数据结构。所有采集器输出 NewsItem，落盘前转为字典。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NewsItem:
    id: str                      # 稳定去重键：<source>:<原始id>
    title: str
    url: str = ""
    source: str = ""             # 数据源代码，如 cls / reddit
    source_name: str = ""        # 数据源展示名
    author: str = ""
    summary: str = ""
    content: str = ""
    published_at: str = ""       # ISO 8601，带时区
    published_date: str = ""     # YYYY-MM-DD（按配置时区）
    fetched_at: str = ""         # 抓取时间 ISO 8601
    crawl_date: str = ""         # 归档日期 YYYY-MM-DD
    lang: str = "zh"
    category: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NewsItem":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass
class SourceResult:
    """单个数据源的采集结果，便于在归档文件中记录健康状态。"""
    name: str
    status: str = "ok"           # ok / skipped / error
    count: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
