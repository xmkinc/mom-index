"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def make_post():
    """Factory for creating raw post dictionaries."""

    def _make(
        post_id: str = "p1",
        title: str = "",
        content: str = "",
        platform: str = "guba",
        url: str = "https://guba.eastmoney.com/news,000001,1.html",
    ) -> dict:
        return {
            "id": post_id,
            "title": title,
            "content": content,
            "platform": platform,
            "url": url,
        }

    return _make


@pytest.fixture
def buy_post(make_post):
    return make_post(
        post_id="buy1",
        title="小白第一次买纳指，还能上车吗",
        content="不懂怎么看，求大佬指点，现在入手会不会太高？",
    )


@pytest.fixture
def sell_post(make_post):
    return make_post(
        post_id="sell1",
        title="黄金亏麻了，要不要割肉",
        content="小白好慌，跌了这么多还能留吗？",
    )


@pytest.fixture
def neutral_post(make_post):
    return make_post(
        post_id="neutral1",
        title="市场分析观点",
        content="从基本面和估值角度看，当前处于合理区间。",
    )


@pytest.fixture
def spam_post(make_post):
    return make_post(
        post_id="spam1",
        title="签到领金条",
        content="我是冲着金条来的，打卡。",
    )


@pytest.fixture
def pro_post(make_post):
    return make_post(
        post_id="pro1",
        title="ETF估值与定投策略分析",
        content="当前PE处于历史分位低位，建议按仓位分散配置，长期持有。",
    )
