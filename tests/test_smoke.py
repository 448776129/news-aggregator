"""基础回归测试：解析逻辑、去重合并、查询过滤。"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app import storage
from app.collectors.jin10 import Jin10Collector
from app.collectors.sina import SinaCollector
from app.models import NewsItem
from app.utils import parse_feed
from app import query


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>测试标题</title><link>https://example.org/a</link>
<description>摘要</description><pubDate>Sun, 22 Nov 2026 10:00:00 +0800</pubDate></item>
</channel></rss>"""

SINA_JSON = {
    "result": {
        "status": {"code": 0},
        "data": [
            {
                "id": "1",
                "title": "新浪财经测试",
                "url": "https://finance.sina.com.cn/a.shtml",
                "ctime": "1763786400",
                "intro": "摘要",
                "media_name": "新浪财经",
            }
        ],
    }
}

JIN10_JS = 'var newest = [{"id":"abc","time":"2026-11-22 11:00:00","data":{"content":"快讯内容"}}];'


class ParsingTests(unittest.TestCase):
    def test_parse_feed(self):
        entries = parse_feed(RSS)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "测试标题")
        self.assertEqual(entries[0]["url"], "https://example.org/a")

    def test_sina_api(self):
        with patch("app.collectors.sina.get_json", return_value=SINA_JSON):
            items = SinaCollector()._from_api()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "新浪财经测试")

    def test_jin10_js(self):
        rows = Jin10Collector._parse_js(JIN10_JS)
        self.assertEqual(rows[0]["id"], "abc")
        items = Jin10Collector._to_items(rows)
        self.assertEqual(items[0].title, "快讯内容")

    def test_merge_items(self):
        a = NewsItem(id="x:1", title="旧", fetched_at="2026-11-22T10:00:00+08:00").to_dict()
        b = NewsItem(id="x:1", title="新", fetched_at="2026-11-22T11:00:00+08:00").to_dict()
        merged = storage.merge_items([a], [b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["title"], "新")

    def test_query_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(storage, "DATA_DIR", tmp):
                payload = {
                    "date": "2026-11-22",
                    "category": "finance",
                    "items": [
                        NewsItem(
                            id="cls:1",
                            title="央行降息",
                            summary="市场关注",
                            source="cls",
                            published_at="2026-11-22T09:00:00+08:00",
                        ).to_dict(),
                        NewsItem(
                            id="sina:2",
                            title="科技新闻",
                            summary="AI",
                            source="sina",
                            published_at="2026-11-22T08:00:00+08:00",
                        ).to_dict(),
                    ],
                }
                storage._write_json(os.path.join(tmp, "2026-11-22", "finance.json"), payload)
                result = query.query_news(date="2026-11-22", category="finance", keyword="央行")
                self.assertEqual(result["count"], 1)
                self.assertEqual(result["items"][0]["source"], "cls")


if __name__ == "__main__":
    unittest.main()
