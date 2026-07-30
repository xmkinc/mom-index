"""Small, explicit-only demo source for local UI and pipeline exercises."""

from __future__ import annotations

from mom_index.config import SOURCE_LABELS, isoformat_utc

from . import SourceResult

_DEMO_POSTS = {
    "nasdaq": [
        ("纳指还能上车吗，小白求教", "第一次买美股ETF，现在入手会不会太高？"),
        ("听朋友说纳指长期稳赚", "朋友都在买，我也想买一点试试。"),
    ],
    "gold": [
        ("黄金亏了要不要割肉", "小白好慌，跌了这么多还能留吗？"),
        ("第一次买黄金怎么选", "请问黄金ETF怎么买，完全不懂。"),
    ],
    "cpo": [
        ("CPO是什么还能买吗", "最近都在说CPO，小白想上车。"),
        ("通信ETF又涨了", "后悔没买，现在追还来得及吗？"),
    ],
    "semiconductor": [
        ("芯片ETF可以买吗", "第一次投资，想买一点半导体试试。"),
        ("半导体涨疯了要不要追", "博主说还会涨，我有点心动。"),
    ],
}


def collect_simulated() -> SourceResult:
    """Return clearly labeled demo posts; callers must opt in explicitly."""

    collected_at = isoformat_utc()
    posts = {
        sector: [
            {
                "id": f"demo_{sector}_{index}",
                "title": title,
                "content": content,
                "url": "",
                "platform": "simulated",
                "collected_at": collected_at,
            }
            for index, (title, content) in enumerate(items)
        ]
        for sector, items in _DEMO_POSTS.items()
    }
    return SourceResult(
        source_id="xiaohongshu",
        label=SOURCE_LABELS["xiaohongshu"],
        mode="simulated",
        posts=posts,
        collected_at=collected_at,
        errors=["explicit local demo data; not a live source"],
    )
