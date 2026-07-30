"""Tests for the Guba HTML parser without live network access."""

from __future__ import annotations

import pytest

from mom_index.collectors.guba import parse_posts


GUBA_HTML = """
<!DOCTYPE html>
<html>
<head><title>股吧</title></head>
<body>
<div class="articleh listitem">
    <span class="l1">1234</span>
    <span class="l2">5</span>
    <span class="l3"><a href="news,000001,1.html" title="小白第一次买，还能上车吗">小白第一次买，还能上车吗</a></span>
    <span class="l5">07-30</span>
</div>
<div class="articleh listitem">
    <span class="l1">567</span>
    <span class="l2">2</span>
    <span class="l3"><a href="news,000001,2.html">黄金亏麻了要不要割肉</a></span>
    <span class="l5">07-29</span>
</div>
<tr>
    <td class="l1">89</td>
    <td class="l2">0</td>
    <td class="l3"><a href="news,000001,3.html" title="纳指长期持有分析">纳指长期持有分析</a></td>
    <td class="l5">07-28</td>
</tr>
<div class="articleh listitem">
    <span class="l1">0</span>
    <span class="l2">0</span>
    <span class="l3"><a href="/a/clickstartsearch">点击开始搜索</a></span>
    <span class="l5">07-27</span>
</div>
</body>
</html>
"""


class TestGubaParser:
    """Row-scoped parsing must keep fields aligned and ignore noise rows."""

    def test_parses_title_and_href(self):
        posts = parse_posts(GUBA_HTML, collected_at="2026-07-30T12:00:00+00:00")
        assert len(posts) == 3
        assert posts[0]["title"] == "小白第一次买，还能上车吗"
        assert posts[0]["url"] == "https://guba.eastmoney.com/news,000001,1.html"

    def test_parses_reads_and_replies(self):
        posts = parse_posts(GUBA_HTML)
        assert posts[0]["reads"] == "1234"
        assert posts[0]["replies"] == "5"
        assert posts[1]["reads"] == "567"
        assert posts[1]["replies"] == "2"

    def test_generates_stable_id(self):
        posts = parse_posts(GUBA_HTML)
        assert all(post["id"].startswith("guba_") for post in posts)
        assert len({post["id"] for post in posts}) == len(posts)

    def test_ignores_search_placeholder(self):
        posts = parse_posts(GUBA_HTML)
        assert not any("点击开始搜索" in post["title"] for post in posts)

    def test_rejects_invalid_url(self):
        html = '''
        <div class="articleh listitem">
            <span class="l3"><a href="https://evil.example.com/news,1.html">bad</a></span>
        </div>
        '''
        posts = parse_posts(html)
        assert posts == []

    def test_empty_html(self):
        assert parse_posts("") == []
