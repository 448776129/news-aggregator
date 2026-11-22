"""带重试与超时控制的 HTTP 客户端。任何失败都返回 None，由采集器决定降级。"""
from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import USER_AGENT

logger = logging.getLogger("newsagg.http")

_session = requests.Session()
_retry = Retry(
    total=2,
    connect=2,
    read=2,
    status=2,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retry)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)
_session.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml, text/xml, text/html, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
)


def get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 12,
    session: requests.Session | None = None,
) -> requests.Response | None:
    client = session or _session
    try:
        resp = client.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code >= 400:
            logger.warning("HTTP %s %s -> %s", resp.status_code, url, resp.text[:120])
            return None
        return resp
    except requests.RequestException as exc:
        logger.warning("请求失败 %s: %s", url, exc)
        return None


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 12,
    session: requests.Session | None = None,
) -> Any | None:
    resp = get(url, params=params, headers=headers, timeout=timeout, session=session)
    if resp is None:
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning("响应不是 JSON: %s", url)
        return None


def get_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 12,
    session: requests.Session | None = None,
) -> str | None:
    resp = get(url, params=params, headers=headers, timeout=timeout, session=session)
    if resp is None:
        return None
    resp.encoding = resp.encoding or resp.apparent_encoding
    return resp.text
