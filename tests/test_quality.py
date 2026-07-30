"""Tests for deterministic sample-quality computation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mom_index.analysis.classifier import analyze_sector
from mom_index.analysis.quality import compute_sample_quality


@pytest.fixture
def quality_now() -> datetime:
    return datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


class TestEmptySample:
    def test_empty_input_is_low_confidence(self, quality_now):
        quality = compute_sample_quality([], [], quality_now)
        assert quality["confidence"] == "low"
        assert "empty_sample" in quality["reason_codes"]
        assert quality["valid_sample_size"] == 0


class TestTitleOnlySample:
    def test_95_title_only_is_low_confidence(self, title_only_posts, quality_now):
        posts = title_only_posts(95)
        results = analyze_sector(posts, "nasdaq")
        quality = compute_sample_quality(posts, results, quality_now)
        assert quality["confidence"] == "low"
        assert quality["title_only_ratio"] == 1.0
        assert "title_only_ratio_above_0_8" in quality["reason_codes"]
        assert quality["valid_sample_size"] == 95


class TestConfidenceGates:
    def test_high_confidence(self, make_post, quality_now):
        posts = [
            make_post(
                post_id=f"p{i}",
                title="小白第一次买，还能上车吗",
                content="不懂怎么看，求大佬指点。",
                platform="guba",
            )
            for i in range(60)
        ]
        # Attach known in-window timestamps.
        for post in posts:
            post["published_at"] = (quality_now - timedelta(hours=1)).isoformat()
        results = analyze_sector(posts, "nasdaq")
        quality = compute_sample_quality(posts, results, quality_now)
        assert quality["confidence"] == "high"
        assert quality["valid_sample_size"] == 60
        assert quality["title_only_ratio"] == 0.0
        assert quality["classifier_evidence_coverage"] >= 0.5
        assert quality["known_in_window_ratio"] == 1.0
        assert quality["reason_codes"] == []

    def test_medium_confidence(self, make_post, quality_now):
        posts = [
            make_post(
                post_id=f"p{i}",
                title="小白第一次买，还能上车吗",
                content="不懂怎么看。",
                platform="guba",
            )
            for i in range(40)
        ]
        for post in posts:
            post["published_at"] = (quality_now - timedelta(hours=1)).isoformat()
        results = analyze_sector(posts, "nasdaq")
        quality = compute_sample_quality(posts, results, quality_now)
        assert quality["confidence"] == "medium"
        assert "sample_size_below_60" in quality["reason_codes"]

    def test_low_confidence_from_evidence_coverage(self, make_post, quality_now):
        posts = [
            make_post(
                post_id=f"p{i}",
                title=f"观察第{i}天",
                content="今天市场有一些波动，整体在关注中。",
            )
            for i in range(35)
        ]
        for post in posts:
            post["published_at"] = (quality_now - timedelta(hours=1)).isoformat()
        results = analyze_sector(posts, "nasdaq")
        quality = compute_sample_quality(posts, results, quality_now)
        assert quality["confidence"] == "low"
        assert quality["title_only_ratio"] <= 0.8
        assert "classifier_evidence_coverage_below_0_3" in quality["reason_codes"]

    def test_unknown_time_counts_toward_unknown_ratio(self, make_post, quality_now):
        posts = [
            make_post(
                post_id="u1",
                title="小白第一次买，还能上车吗",
                content="不懂怎么看。",
            )
        ]
        results = analyze_sector(posts, "nasdaq")
        quality = compute_sample_quality(posts, results, quality_now)
        assert quality["unknown_time_ratio"] == 1.0
        assert quality["known_in_window_ratio"] == 0.0
        assert "known_in_window_ratio_below_0_6" in quality["reason_codes"]

    def test_spam_excluded_from_quality(self, make_post, quality_now):
        posts = [
            make_post(post_id="spam", title="签到领金条", content=""),
            make_post(
                post_id="valid",
                title="小白第一次买，还能上车吗",
                content="不懂怎么看。",
            ),
        ]
        results = analyze_sector(posts, "nasdaq")
        quality = compute_sample_quality(posts, results, quality_now)
        assert quality["valid_sample_size"] == 1
        assert quality["title_only_ratio"] == 0.0
