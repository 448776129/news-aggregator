"""通用工具：时间解析、RSS/Atom 解析、文本清洗。"""
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from .config import TZ


def local_now() -> datetime:
    return datetime.now(TZ)


def today_str() -> str:
    return local_now().strftime("%Y-%m-%d")


def parse_datetime(value: Any) -> datetime | None:
    """把各种常见时间表示解析为带时区的 datetime（按 NEWS_TIMEZONE）。"""
    if value in (None, "", 0):
        return None
    dt: datetime | None = None
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        elif isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            text = value.strip()
            if re.fullmatch(r"-?\d{9,13}", text):
                num = int(text)
                if len(text) == 13:
                    num /= 1000
                dt = datetime.fromtimestamp(num, tz=timezone.utc)
            else:
                try:
                    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        dt = parsedate_to_datetime(text)
                    except (TypeError, ValueError):
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
                            try:
                                dt = datetime.strptime(text, fmt)
                                break
                            except ValueError:
                                continue
    except (ValueError, OverflowError, OSError):
        return None

    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def iso(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


def day(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else ""


def clean_html(text: Any, limit: int | None = None) -> str:
    """清洗 HTML；默认不截断，保证采集到完整正文。

    仅在明确传入 limit（如标题限制 300 字）时才截断。
    """
    if not text:
        return ""
    if isinstance(text, (list, tuple)):
        text = " ".join(str(t) for t in text)
    value = html.unescape(str(text))
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] if limit else value


def stable_id(source: str, raw: Any) -> str:
    raw_str = str(raw or "")
    key = f"{source}:{raw_str}"
    if len(key) > 180:
        key = f"{source}:{hashlib.sha1(raw_str.encode('utf-8')).hexdigest()}"
    return key


def _local(tag: str) -> str:
    return tag.split("}")[-1].lower()


def _find_text(elem: ET.Element, names: Iterable[str]) -> str:
    wanted = {n.lower() for n in names}
    for child in elem.iter():
        if _local(child.tag) in wanted and child.text and child.text.strip():
            return child.text.strip()
    return ""


def _find_link(elem: ET.Element) -> str:
    for child in elem.iter():
        if _local(child.tag) != "link":
            continue
        href = child.get("href")
        if href:
            return href.strip()
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def parse_feed(content: bytes | str) -> list[dict[str, str]]:
    """解析 RSS 2.0 / Atom，返回统一字典列表。"""
    if isinstance(content, str):
        content = content.encode("utf-8", errors="ignore")
    try:
        # 去掉可能存在的 XML 声明编码声明冲突
        content = re.sub(rb"^<\?xml[^>]*\?>", b"", content.lstrip(), count=1)
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    entries = [e for e in root.iter() if _local(e.tag) in ("item", "entry")]
    results: list[dict[str, str]] = []
    for entry in entries:
        title = _find_text(entry, ("title",))
        if not title:
            continue
        results.append(
            {
                "title": clean_html(title, 300),
                "url": _find_link(entry),
                "summary": _find_text(entry, ("description", "summary", "content")),
                "published": _find_text(entry, ("pubdate", "published", "updated", "date")),
                "author": _find_text(entry, ("author", "creator")),
            }
        )
    return results


def pick(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return default
