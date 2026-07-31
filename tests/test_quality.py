"""Tests for deterministic sample-quality computation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from mom_index.analysis.classifier import analyze_sector
from mom_index.analysis.quality import CANONICAL_REASON_CODES, compute_sample_quality

# The fixed, documented gate order (empty_sample is canonical but numeric-gate-free).
EXPECTED_GATE_ORDER = (
    "sample_size_below_30",
    "sample_size_below_60",
    "title_only_ratio_above_0_8",
    "title_only_ratio_above_0_4",
    "classifier_evidence_coverage_below_0_3",
    "classifier_evidence_coverage_below_0_5",
    "known_in_window_ratio_below_0_6",
)


@pytest.fixture
def quality_now() -> datetime:
    return datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


def _make_sample(
    count: int,
    now: datetime,
    *,
    title_only: int = 0,
    with_evidence: int | None = None,
    in_window: int | None = None,
) -> tuple[list[dict], list[SimpleNamespace]]:
    """Posts and classifier results with exact aggregate counts."""
    with_evidence = count if with_evidence is None else with_evidence
    in_window = count if in_window is None else in_window
    posts = []
    results = []
    for i in range(count):
        post = {"id": f"s{i}", "platform": "guba"}
        if i < in_window:
            post["published_at"] = (now - timedelta(hours=1)).isoformat()
        posts.append(post)
        results.append(
            SimpleNamespace(
                post_id=f"s{i}",
                level="纯小白",
                has_content=i >= title_only,
                matched_newbie=["小白"] if i < with_evidence else [],
                matched_pro=[],
                matched_extension_signals=[],
                platform="guba",
            )
        )
    return posts, results


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


class TestCanonicalReasonCodes:
    def test_vocabulary_and_order_are_locked(self):
        assert CANONICAL_REASON_CODES == (
            "empty_sample",
            "sample_size_below_30",
            "sample_size_below_60",
            "title_only_ratio_above_0_8",
            "title_only_ratio_above_0_4",
            "classifier_evidence_coverage_below_0_3",
            "classifier_evidence_coverage_below_0_5",
            "known_in_window_ratio_below_0_6",
        )

    def test_empty_sample_reason_codes_are_unchanged(self, quality_now):
        quality = compute_sample_quality([], [], quality_now)
        assert quality["confidence"] == "low"
        assert quality["reason_codes"] == [
            "empty_sample",
            "sample_size_below_30",
            "sample_size_below_60",
            "classifier_evidence_coverage_below_0_3",
            "known_in_window_ratio_below_0_6",
        ]

    def test_emitted_codes_stay_inside_canonical_vocabulary(self, quality_now):
        samples = [
            compute_sample_quality([], [], quality_now),
            compute_sample_quality(
                *_make_sample(35, quality_now, title_only=35, with_evidence=0),
                quality_now,
            ),
            compute_sample_quality(
                *_make_sample(45, quality_now, title_only=27, with_evidence=18, in_window=9),
                quality_now,
            ),
        ]
        for quality in samples:
            assert set(quality["reason_codes"]) <= set(CANONICAL_REASON_CODES)


class TestQualityGates:
    def test_gate_order_and_shape_are_locked(self, quality_now):
        posts, results = _make_sample(60, quality_now)
        quality = compute_sample_quality(posts, results, quality_now)
        assert [gate["code"] for gate in quality["gates"]] == list(EXPECTED_GATE_ORDER)
        for gate in quality["gates"]:
            assert set(gate) == {
                "code", "level", "passed", "actual", "threshold", "comparator",
            }
        assert set(EXPECTED_GATE_ORDER) < set(CANONICAL_REASON_CODES)

    def test_high_confidence_gate_values(self, quality_now):
        posts, results = _make_sample(60, quality_now)
        quality = compute_sample_quality(posts, results, quality_now)
        assert quality["confidence"] == "high"
        assert quality["reason_codes"] == []
        assert quality["gates"] == [
            {"code": "sample_size_below_30", "level": "low", "passed": True, "actual": 60, "threshold": 30, "comparator": "gte"},
            {"code": "sample_size_below_60", "level": "high", "passed": True, "actual": 60, "threshold": 60, "comparator": "gte"},
            {"code": "title_only_ratio_above_0_8", "level": "low", "passed": True, "actual": 0.0, "threshold": 0.8, "comparator": "lte"},
            {"code": "title_only_ratio_above_0_4", "level": "high", "passed": True, "actual": 0.0, "threshold": 0.4, "comparator": "lte"},
            {"code": "classifier_evidence_coverage_below_0_3", "level": "low", "passed": True, "actual": 1.0, "threshold": 0.3, "comparator": "gte"},
            {"code": "classifier_evidence_coverage_below_0_5", "level": "high", "passed": True, "actual": 1.0, "threshold": 0.5, "comparator": "gte"},
            {"code": "known_in_window_ratio_below_0_6", "level": "high", "passed": True, "actual": 1.0, "threshold": 0.6, "comparator": "gte"},
        ]

    def test_empty_sample_has_no_fabricated_numeric_gate(self, quality_now):
        quality = compute_sample_quality([], [], quality_now)
        codes = [gate["code"] for gate in quality["gates"]]
        assert "empty_sample" not in codes
        assert codes == list(EXPECTED_GATE_ORDER)
        by_code = {gate["code"]: gate for gate in quality["gates"]}
        assert by_code["sample_size_below_30"]["passed"] is False
        assert by_code["sample_size_below_30"]["actual"] == 0
        assert by_code["title_only_ratio_above_0_8"]["passed"] is True

    @pytest.mark.parametrize(
        ("count", "passed_30", "passed_60", "confidence"),
        [
            (29, False, False, "low"),
            (30, True, False, "medium"),
            (59, True, False, "medium"),
            (60, True, True, "high"),
        ],
    )
    def test_sample_size_boundaries(self, quality_now, count, passed_30, passed_60, confidence):
        posts, results = _make_sample(count, quality_now)
        quality = compute_sample_quality(posts, results, quality_now)
        by_code = {gate["code"]: gate for gate in quality["gates"]}
        assert by_code["sample_size_below_30"]["passed"] is passed_30
        assert by_code["sample_size_below_60"]["passed"] is passed_60
        assert by_code["sample_size_below_30"]["actual"] == count
        assert quality["confidence"] == confidence
        assert ("sample_size_below_30" in quality["reason_codes"]) is not passed_30
        assert ("sample_size_below_60" in quality["reason_codes"]) is not passed_60

    def test_title_only_boundary_at_exact_thresholds(self, quality_now):
        # Exactly 0.8: the strict > 0.8 low test does not fire, so the low
        # gate passes while the <= 0.4 high gate fails.
        posts, results = _make_sample(60, quality_now, title_only=48)
        quality = compute_sample_quality(posts, results, quality_now)
        by_code = {gate["code"]: gate for gate in quality["gates"]}
        assert quality["title_only_ratio"] == 0.8
        assert by_code["title_only_ratio_above_0_8"]["passed"] is True
        assert by_code["title_only_ratio_above_0_4"]["passed"] is False
        assert by_code["title_only_ratio_above_0_4"]["actual"] == 0.8
        assert quality["confidence"] == "medium"
        assert "title_only_ratio_above_0_8" not in quality["reason_codes"]
        assert "title_only_ratio_above_0_4" in quality["reason_codes"]

        # Just above 0.8 forces low confidence.
        posts, results = _make_sample(60, quality_now, title_only=49)
        quality = compute_sample_quality(posts, results, quality_now)
        by_code = {gate["code"]: gate for gate in quality["gates"]}
        assert by_code["title_only_ratio_above_0_8"]["passed"] is False
        assert by_code["title_only_ratio_above_0_8"]["actual"] == round(49 / 60, 4)
        assert quality["confidence"] == "low"
        assert "title_only_ratio_above_0_8" in quality["reason_codes"]

    def test_evidence_coverage_boundaries(self, quality_now):
        # Exactly 0.3: low gate passes, high gate fails.
        posts, results = _make_sample(60, quality_now, with_evidence=18)
        quality = compute_sample_quality(posts, results, quality_now)
        by_code = {gate["code"]: gate for gate in quality["gates"]}
        assert quality["classifier_evidence_coverage"] == 0.3
        assert by_code["classifier_evidence_coverage_below_0_3"]["passed"] is True
        assert by_code["classifier_evidence_coverage_below_0_5"]["passed"] is False
        assert quality["confidence"] == "medium"
        assert "classifier_evidence_coverage_below_0_3" not in quality["reason_codes"]
        assert "classifier_evidence_coverage_below_0_5" in quality["reason_codes"]

        # Exactly 0.5 satisfies the high gate.
        posts, results = _make_sample(60, quality_now, with_evidence=30)
        quality = compute_sample_quality(posts, results, quality_now)
        by_code = {gate["code"]: gate for gate in quality["gates"]}
        assert by_code["classifier_evidence_coverage_below_0_5"]["passed"] is True
        assert quality["confidence"] == "high"

    def test_known_in_window_boundary(self, quality_now):
        posts, results = _make_sample(60, quality_now, in_window=36)
        quality = compute_sample_quality(posts, results, quality_now)
        by_code = {gate["code"]: gate for gate in quality["gates"]}
        assert quality["known_in_window_ratio"] == 0.6
        assert by_code["known_in_window_ratio_below_0_6"]["passed"] is True
        assert quality["confidence"] == "high"
        assert "known_in_window_ratio_below_0_6" not in quality["reason_codes"]

        posts, results = _make_sample(60, quality_now, in_window=35)
        quality = compute_sample_quality(posts, results, quality_now)
        by_code = {gate["code"]: gate for gate in quality["gates"]}
        assert by_code["known_in_window_ratio_below_0_6"]["passed"] is False
        assert by_code["known_in_window_ratio_below_0_6"]["actual"] == round(35 / 60, 4)
        assert quality["confidence"] == "medium"
        assert "known_in_window_ratio_below_0_6" in quality["reason_codes"]

    def test_existing_fields_are_unchanged_besides_additive_gates(self, quality_now):
        posts, results = _make_sample(
            40, quality_now, title_only=8, with_evidence=20
        )
        quality = compute_sample_quality(posts, results, quality_now)
        without_gates = {key: value for key, value in quality.items() if key != "gates"}
        assert without_gates == {
            "model_version": "1.0",
            "confidence": "medium",
            "valid_sample_size": 40,
            "title_only_ratio": 0.2,
            "platform_counts": {"guba": 40},
            "classifier_evidence_coverage": 0.5,
            "known_in_window_ratio": 1.0,
            "unknown_time_ratio": 0.0,
            "window_hours": 72,
            "reason_codes": ["sample_size_below_60"],
        }
