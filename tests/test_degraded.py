"""Tests for degraded-state and unavailable-source contracts."""

from __future__ import annotations

import os

import pytest

from mom_index.collectors import SourceResult
from mom_index.collectors.guba import GubaCollector
from mom_index.export import build_payload
from mom_index.storage import empty_history
from mom_index.validation import validate_payload


class TestForcedCollectionFailure:
    """Forced failure must produce an unavailable source and schema-valid payload."""

    def test_force_failure_env(self, monkeypatch):
        monkeypatch.setenv("MOM_INDEX_FORCE_COLLECTION_FAILURE", "1")
        result = GubaCollector().collect()
        assert result.mode == "unavailable"
        assert result.collected_at is None
        assert result.errors
        assert result.post_count == 0

    def test_unavailable_source_payload_validates(self):
        result = SourceResult.unavailable("guba", "forced test failure")
        payload = build_payload(empty_history(), [result])
        engine = validate_payload(payload)
        assert "jsonschema" in engine
        assert payload["sources"][0]["mode"] == "unavailable"
        assert payload["sources"][0]["collected_at"] is None
        assert payload["freshness"]["is_stale"] is True

    def test_zero_valid_posts_is_warning_not_success(self):
        # A live collection with zero valid rows should surface a warning
        result = SourceResult(
            source_id="guba",
            label="东方财富股吧",
            mode="unavailable",
            posts={"nasdaq": []},
            errors=["nasdaq: zero valid post rows"],
        )
        payload = build_payload(empty_history(), [result])
        validate_payload(payload)
        assert any("zero" in w.lower() or "unavailable" in w.lower() for w in payload["warnings"])
