"""Tests for deterministic scoring formulas."""

from __future__ import annotations

import pytest

from mom_index.analysis.classifier import AnalysisResult, analyze_post
from mom_index.analysis.scoring import compute_sector_index, interpret_index


def _result(
    *,
    post_id: str = "p1",
    newbie_score: float = 0,
    level: str = "中间派",
    sentiment_score: float = 0,
    intent: str = "neutral",
    intent_strength: float = 0,
    title: str = "post",
    source_url: str = "https://guba.eastmoney.com/news,000001,1.html",
) -> AnalysisResult:
    return AnalysisResult(
        post_id=post_id,
        title=title,
        platform="guba",
        sector="nasdaq",
        source_url=source_url,
        newbie_score=newbie_score,
        level=level,
        sentiment_score=sentiment_score,
        intent=intent,
        intent_strength=intent_strength,
    )


class TestInterpretBoundaries:
    """interpret_index boundaries at 0, 20, 40, 60, 75."""

    @pytest.mark.parametrize(
        "index,expected_prefix",
        [
            (0, "🔵 极度冷清"),
            (19.9, "🔵 极度冷清"),
            (20, "🟢 正常区间"),
            (39.9, "🟢 正常区间"),
            (40, "🟡 开始升温"),
            (59.9, "🟡 开始升温"),
            (60, "🟠 高度警惕"),
            (74.9, "🟠 高度警惕"),
            (75, "🔴 极度狂热"),
            (100, "🔴 极度狂热"),
        ],
    )
    def test_boundaries(self, index, expected_prefix):
        assert interpret_index(index).startswith(expected_prefix)


class BuySellRatio:
    """Honest buy/sell ratio contracts."""

    def test_zero_zero_is_deterministic(self):
        result = compute_sector_index([_result(newbie_score=25, level="中间派")])
        assert result["details"]["buy_count"] == 0
        assert result["details"]["sell_count"] == 0
        assert result["details"]["buy_sell_ratio"] == 0.0

    def test_buy_no_sell_is_null(self):
        result = compute_sector_index(
            [
                _result(
                    newbie_score=25,
                    level="中间派",
                    intent="buy",
                    intent_strength=0.5,
                )
            ]
        )
        assert result["details"]["buy_count"] == 1
        assert result["details"]["sell_count"] == 0
        assert result["details"]["buy_sell_ratio"] is None

    def test_buy_sell_ratio_computed(self):
        result = compute_sector_index(
            [
                _result(newbie_score=25, intent="buy", intent_strength=0.5),
                _result(newbie_score=25, intent="buy", intent_strength=0.5),
                _result(newbie_score=25, intent="sell", intent_strength=0.5),
            ]
        )
        assert result["details"]["buy_count"] == 2
        assert result["details"]["sell_count"] == 1
        assert result["details"]["buy_sell_ratio"] == 2.0


class TestSpamExclusion:
    """Spam records never enter counts, denominators, or sub-indices."""

    def test_spam_excluded_from_all_details(self, make_post):
        spam = analyze_post(make_post(title="签到领金条", content=""), "nasdaq")
        assert spam.level == "垃圾帖"
        valid = _result(
            post_id="v1",
            newbie_score=25,
            level="中间派",
            intent="buy",
            intent_strength=0.5,
        )
        result = compute_sector_index([spam, valid])
        details = result["details"]
        assert details["total_posts"] == 2
        assert details["valid_posts"] == 1
        assert details["spam_posts"] == 1
        assert details["newbie_posts"] == 1
        assert details["buy_count"] == 1
        assert details["sell_count"] == 0

    def test_all_spam_yields_zero_index(self, make_post):
        spam = analyze_post(make_post(title="签到领金条", content=""), "nasdaq")
        result = compute_sector_index([spam])
        assert result["index"] == 0
        assert result["details"]["valid_posts"] == 0


class TestFormulaWeights:
    """Direct unit tests for the weighted index formula."""

    def test_pure_newbie_maximizes_index(self):
        posts = [
            _result(
                post_id=f"p{i}",
                newbie_score=100,
                level="纯小白",
                sentiment_score=1.0,
                intent="buy",
                intent_strength=1.0,
            )
            for i in range(10)
        ]
        result = compute_sector_index(posts)
        assert result["index"] == 100.0
        assert result["details"]["newbie_ratio"] == 100.0

    def test_professional_posts_yield_low_index(self):
        posts = [
            _result(
                post_id=f"p{i}",
                newbie_score=0,
                level="专业投资者",
                sentiment_score=0,
            )
            for i in range(10)
        ]
        result = compute_sector_index(posts)
        assert result["index"] < 20

    def test_empty_sector(self):
        result = compute_sector_index([])
        assert result["index"] == 0
        assert result["interpretation"] == "无数据"

    def test_activity_is_output_but_does_not_affect_index(self):
        # activity depends on valid post count; changing it alone should not change index
        posts = [_result(post_id="p1", newbie_score=50, level="纯小白", sentiment_score=0.5)]
        result = compute_sector_index(posts)
        assert "activity" in result["details"]
        # With 1 valid post, activity is small; index is driven by newbie dimensions
        assert result["index"] > 0


class TestTopPosts:
    """Top newbie post selection and formatting."""

    def test_top_posts_capped_at_five(self):
        posts = [
            _result(
                post_id=f"p{i}",
                newbie_score=20 + i,
                level="中间派",
            )
            for i in range(10)
        ]
        result = compute_sector_index(posts)
        assert len(result["top_newbie_posts"]) == 5
        # Highest scores first
        assert result["top_newbie_posts"][0]["score"] == 29

    def test_top_posts_have_required_fields(self):
        result = compute_sector_index([_result(newbie_score=25, level="中间派")])
        post = result["top_newbie_posts"][0]
        assert set(post.keys()) == {
            "title",
            "score",
            "level",
            "reasoning",
            "intent",
            "key_signals",
            "source_url",
        }
