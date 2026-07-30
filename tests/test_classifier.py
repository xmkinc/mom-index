"""Tests for the deterministic keyword classifier."""

from __future__ import annotations

import pytest

from mom_index.analysis.classifier import (
    AnalysisResult,
    analyze_all,
    analyze_post,
    analyze_sector,
    dedupe_posts,
)


class TestSpamFiltering:
    """Spam posts must be isolated from all downstream metrics."""

    def test_spam_returns_filtered_result(self, spam_post):
        result = analyze_post(spam_post, "nasdaq")
        assert result.level == "垃圾帖"
        assert result.newbie_score == 0
        assert result.intent == "neutral"
        assert result.sentiment_score == 0
        assert result.matched_newbie == []
        assert result.matched_pro == []

    def test_non_spam_analyzed_normally(self, buy_post):
        result = analyze_post(buy_post, "nasdaq")
        assert result.level != "垃圾帖"
        assert result.newbie_score > 0


class TestDeduplication:
    """Duplicate stable identities are counted once per sector."""

    def test_dedupe_keeps_first_occurrence(self, make_post):
        posts = [
            make_post(post_id="a", title="first"),
            make_post(post_id="a", title="second"),
            make_post(post_id="b", title="third"),
        ]
        unique = dedupe_posts(posts)
        assert [p["title"] for p in unique] == ["first", "third"]

    def test_analyze_sector_dedupes_by_id(self, make_post):
        posts = [
            make_post(post_id="dup", title="小白第一次买，还能上车吗"),
            make_post(post_id="dup", title="小白第一次买，还能上车吗"),
            make_post(post_id="uniq", title="黄金跌了要不要割肉"),
        ]
        results = analyze_sector(posts, "nasdaq")
        assert len(results) == 2
        assert {r.post_id for r in results} == {"dup", "uniq"}


class TestIntentMatching:
    """Intent detection avoids overlapping-keyword double counting."""

    def test_overlapping_buy_keywords_count_once(self, make_post):
        # "还能买吗" is a substring match for "买" and exact for "还能买吗"
        post = make_post(title="还能买吗", content="")
        result = analyze_post(post, "nasdaq")
        # Both "买" and "还能买吗" match, but each keyword counted once
        assert result.intent == "buy"

    def test_tie_is_neutral(self, make_post):
        post = make_post(title="观望", content="")
        result = analyze_post(post, "nasdaq")
        assert result.intent == "neutral"
        assert result.intent_strength == 0

    def test_buy_intent(self, buy_post):
        result = analyze_post(buy_post, "nasdaq")
        assert result.intent == "buy"
        assert result.intent_strength > 0

    def test_sell_intent(self, sell_post):
        result = analyze_post(sell_post, "gold")
        assert result.intent == "sell"
        assert result.intent_strength > 0

    def test_neutral_intent(self, neutral_post):
        result = analyze_post(neutral_post, "nasdaq")
        assert result.intent == "neutral"


class TestNewbieScoring:
    """Newbie/professional classification boundaries."""

    def test_pro_post_scores_low(self, pro_post):
        result = analyze_post(pro_post, "nasdaq")
        assert result.level in {"偏专业", "专业投资者"}
        assert result.newbie_score < 20

    def test_newbie_post_scores_high(self, buy_post):
        result = analyze_post(buy_post, "nasdaq")
        assert result.newbie_score >= 20
        assert "小白" in result.level


class TestAnalyzeAll:
    """Cross-sector batch analysis."""

    def test_analyzes_all_sectors(self, buy_post, sell_post):
        sector_data = {
            "nasdaq": [buy_post],
            "gold": [sell_post],
            "cpo": [],
            "semiconductor": [],
        }
        results = analyze_all(sector_data)
        assert set(results.keys()) == {"nasdaq", "gold", "cpo", "semiconductor"}
        assert len(results["nasdaq"]) == 1
        assert len(results["gold"]) == 1
        assert results["cpo"] == []
        assert results["semiconductor"] == []

    def test_sorting_is_deterministic(self, make_post):
        posts = [
            make_post(post_id="z", title="小白第一次买，还能上车吗"),
            make_post(post_id="a", title="小白第一次买，还能上车吗"),
        ]
        results = analyze_sector(posts, "nasdaq")
        # Same score: sorted by post_id ascending
        assert [r.post_id for r in results] == ["a", "z"]


class TestPlatformExtensions:
    """Platform-scoped keyword extensions affect only the matching platform."""

    def test_xhs_help_phrases_produce_evidence(self, xhs_help_post):
        result = analyze_post(xhs_help_post, "nasdaq")
        assert result.matched_extension_signals
        labels = {item[0] for item in result.matched_extension_signals}
        assert "知识求助" in labels
        assert "决策依赖" in labels

    def test_xhs_extensions_do_not_apply_to_guba(self, make_post):
        post = make_post(
            post_id="g1",
            title="小白不会选股怎么办",
            content="求带，现在入局还不晚吗？",
            platform="guba",
        )
        result = analyze_post(post, "nasdaq")
        assert result.matched_extension_signals == []

    def test_has_content_flag(self, make_post):
        with_content = make_post(post_id="c1", title="标题", content="正文")
        without_content = make_post(post_id="c2", title="标题", content="")
        assert analyze_post(with_content, "nasdaq").has_content is True
        assert analyze_post(without_content, "nasdaq").has_content is False


class TestCompoundOverrides:
    """Ordered longest-match compound overrides suppress inner matches."""

    def test_chaodi_shibai_is_sell_not_buy(self, make_post):
        post = make_post(
            post_id="compound1",
            title="抄底失败被套了",
            content="现在怎么办",
            platform="xiaohongshu",
        )
        result = analyze_post(post, "nasdaq")
        assert result.intent == "sell"
        # Ordinary 抄底 buy signal is suppressed by the compound override.
        buy_hits = [kw for kw in ("抄底",) if kw in f"{post['title']} {post['content']}"]
        # The only buy keyword in the text is the substring of the override.
        assert "抄底" in f"{post['title']} {post['content']}"
        assert result.sentiment_score <= 0

    def test_xhs_panic_post_is_sell_side(self, xhs_panic_post):
        result = analyze_post(xhs_panic_post, "nasdaq")
        assert result.intent == "sell"
        assert result.sentiment_score < 0
