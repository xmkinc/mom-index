"""Tests for history storage and last-known-good preservation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mom_index.config import display_date
from mom_index.storage import (
    dominant_source_mode,
    empty_history,
    load_history,
    merge_success,
    save_history,
)


def _sector_indices() -> dict:
    return {
        "nasdaq": {"index": 10.0, "interpretation": "test", "details": {}},
        "gold": {"index": 20.0, "interpretation": "test", "details": {}},
        "cpo": {"index": 30.0, "interpretation": "test", "details": {}},
        "semiconductor": {"index": 40.0, "interpretation": "test", "details": {}},
    }


class TestHistoryLifecycle:
    """Loading, merging, and persisting history."""

    def test_empty_history(self):
        history = empty_history()
        assert history["schema_version"] == 3
        assert history["last_success_at"] is None
        assert history["records"] == []

    def test_load_history_missing_file(self, tmp_path: Path):
        assert load_history(tmp_path) == empty_history()

    def test_merge_success_adds_record(self):
        history = empty_history()
        collected_at = "2026-07-30T12:00:00+00:00"
        history = merge_success(history, _sector_indices(), collected_at=collected_at, source_mode="live")
        assert history["last_success_at"] == collected_at
        assert len(history["records"]) == 1
        assert history["records"][0]["date"] == display_date(datetime.fromisoformat(collected_at))

    def test_merge_success_replaces_same_day_record(self):
        history = empty_history()
        # 00:00 UTC and 08:00 UTC are both 2026-07-30 in Asia/Shanghai
        collected_at_1 = "2026-07-30T00:00:00+00:00"
        collected_at_2 = "2026-07-30T08:00:00+00:00"
        history = merge_success(history, _sector_indices(), collected_at=collected_at_1, source_mode="live")
        history = merge_success(history, _sector_indices(), collected_at=collected_at_2, source_mode="live")
        assert len(history["records"]) == 1
        assert history["records"][0]["timestamp"] == collected_at_2

    def test_merge_success_keeps_different_days(self):
        history = empty_history()
        history = merge_success(history, _sector_indices(), collected_at="2026-07-29T12:00:00+00:00", source_mode="live")
        history = merge_success(history, _sector_indices(), collected_at="2026-07-30T12:00:00+00:00", source_mode="live")
        assert len(history["records"]) == 2

    def test_merge_success_requires_all_sectors(self):
        history = empty_history()
        incomplete = {k: v for k, v in _sector_indices().items() if k != "nasdaq"}
        with pytest.raises(ValueError, match="missing sectors"):
            merge_success(history, incomplete, collected_at="2026-07-30T12:00:00+00:00", source_mode="live")

    def test_merge_success_rejects_unavailable_mode(self):
        history = empty_history()
        with pytest.raises(
            ValueError,
            match="Only live, imported, or explicit simulated",
        ):
            merge_success(
                history,
                _sector_indices(),
                collected_at="2026-07-30T12:00:00+00:00",
                source_mode="unavailable",
            )

    def test_merge_success_accepts_imported_mode(self):
        history = merge_success(
            empty_history(),
            _sector_indices(),
            collected_at="2026-07-30T12:00:00+00:00",
            source_mode="imported",
        )
        assert history["records"][0]["source_mode"] == "imported"
        assert history["records"][0]["sectors"]["nasdaq"]["sample_quality"] is None

    def test_load_v2_history_upgrades_additively(self, tmp_path: Path):
        legacy = {
            "schema_version": 2,
            "last_success_at": "2026-07-30T12:00:00+00:00",
            "records": [
                {
                    "date": "2026-07-30",
                    "timestamp": "2026-07-30T12:00:00+00:00",
                    "source_mode": "live",
                    "sectors": _sector_indices(),
                }
            ],
        }
        save_history(tmp_path, legacy)
        loaded = load_history(tmp_path)
        assert loaded["schema_version"] == 3
        assert loaded["records"][0]["sectors"]["gold"]["sample_quality"] is None

    @pytest.mark.parametrize(
        "modes,expected",
        [
            (["live"], "live"),
            (["live", "imported"], "imported"),
            (["imported", "simulated", "live"], "simulated"),
        ],
    )
    def test_dominant_source_mode(self, modes, expected):
        assert dominant_source_mode(modes) == expected

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        history = empty_history()
        history = merge_success(history, _sector_indices(), collected_at="2026-07-30T12:00:00+00:00", source_mode="live")
        save_history(tmp_path, history)
        loaded = load_history(tmp_path)
        assert loaded == history
