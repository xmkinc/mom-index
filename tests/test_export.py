"""Tests for public payload export, schema validation, and privacy."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mom_index.collectors import SourceResult
from mom_index.export import build_payload
from mom_index.storage import empty_history, merge_success
from mom_index.validation import PayloadValidationError, validate_payload


def _live_result() -> SourceResult:
    return SourceResult(
        source_id="guba",
        label="东方财富股吧",
        mode="live",
        posts={"nasdaq": [{"id": "1", "title": "t"}]},
        collected_at="2026-07-30T12:00:00+00:00",
    )


def _unavailable_result() -> SourceResult:
    return SourceResult.unavailable("guba", "network unreachable")


def _simulated_result() -> SourceResult:
    from mom_index.collectors.simulated import collect_simulated

    return collect_simulated()


def _valid_details() -> dict:
    return {
        "total_posts": 1,
        "valid_posts": 1,
        "spam_posts": 0,
        "newbie_posts": 1,
        "pure_newbie": 0,
        "newbie_ratio": 100.0,
        "avg_newbie_score": 25.0,
        "avg_sentiment": 0.0,
        "purity_signal": 0.0,
        "activity": 1.2,
        "mom_buy_index": 0.0,
        "mom_sell_index": 0.0,
        "buy_sell_ratio": 0.0,
        "buy_count": 0,
        "sell_count": 0,
    }


def _history() -> dict:
    history = empty_history()
    sectors = {
        "nasdaq": {"index": 10.0, "interpretation": "test", "details": _valid_details(), "top_newbie_posts": []},
        "gold": {"index": 20.0, "interpretation": "test", "details": _valid_details(), "top_newbie_posts": []},
        "cpo": {"index": 30.0, "interpretation": "test", "details": _valid_details(), "top_newbie_posts": []},
        "semiconductor": {"index": 40.0, "interpretation": "test", "details": _valid_details(), "top_newbie_posts": []},
    }
    return merge_success(history, sectors, collected_at="2026-07-30T12:00:00+00:00", source_mode="live")


class TestSchemaValidation:
    """Exported payloads must validate against schema v2."""

    def test_live_payload_validates(self):
        payload = build_payload(_history(), [_live_result()])
        engine = validate_payload(payload)
        assert "jsonschema" in engine

    def test_unavailable_payload_validates(self):
        payload = build_payload(empty_history(), [_unavailable_result()])
        engine = validate_payload(payload)
        assert "jsonschema" in engine
        assert payload["freshness"]["is_stale"] is True

    def test_simulated_payload_has_warning(self):
        payload = build_payload(empty_history(), [_simulated_result()])
        engine = validate_payload(payload)
        assert "jsonschema" in engine
        assert any("simulated" in w.lower() for w in payload["warnings"])


class TestPrivacy:
    """Public payload must not leak private fields."""

    def test_no_author_fields(self):
        payload = build_payload(_history(), [_live_result()])
        with pytest.raises(PayloadValidationError, match="Private field"):
            polluted = dict(payload)
            polluted["author"] = "leak"
            validate_payload(polluted)

    def test_no_secret_values(self):
        payload = build_payload(_history(), [_live_result()])
        with pytest.raises(PayloadValidationError, match="Secret-like"):
            polluted = dict(payload)
            polluted["warnings"] = ["api_key=secret123"]
            validate_payload(polluted)


class TestFreshness:
    """Freshness and staleness semantics."""

    def test_stale_when_last_success_old(self):
        old = "2026-07-29T00:00:00+00:00"
        history = empty_history()
        history["last_success_at"] = old
        payload = build_payload(history, [_live_result()], generated_at=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
        assert payload["freshness"]["is_stale"] is True

    def test_fresh_when_last_success_recent(self):
        recent = "2026-07-30T10:00:00+00:00"
        history = empty_history()
        history["last_success_at"] = recent
        payload = build_payload(history, [_live_result()], generated_at=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
        assert payload["freshness"]["is_stale"] is False
