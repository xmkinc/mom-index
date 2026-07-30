"""Tests for timezone-aware timestamps and Shanghai day boundary."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mom_index.config import display_date, isoformat_utc
from mom_index.storage import merge_success


def _sector_indices() -> dict:
    return {
        "nasdaq": {"index": 10.0, "interpretation": "test", "details": {}},
        "gold": {"index": 20.0, "interpretation": "test", "details": {}},
        "cpo": {"index": 30.0, "interpretation": "test", "details": {}},
        "semiconductor": {"index": 40.0, "interpretation": "test", "details": {}},
    }


class TestShanghaiDayBoundary:
    """Record dates follow Asia/Shanghai day boundary."""

    @pytest.mark.parametrize(
        "utc_hour,expected_date",
        [
            (0, "2026-07-30"),   # 08:00 Shanghai same day
            (7, "2026-07-30"),   # 15:00 Shanghai same day
            (15, "2026-07-30"),  # 23:00 Shanghai same day
            (16, "2026-07-31"),  # 00:00 Shanghai next day
            (23, "2026-07-31"),  # 07:00 Shanghai next day
        ],
    )
    def test_day_boundary(self, utc_hour, expected_date):
        ts = f"2026-07-30T{utc_hour:02d}:00:00+00:00"
        history = merge_success(
            {"schema_version": 2, "last_success_at": None, "records": []},
            _sector_indices(),
            collected_at=ts,
            source_mode="live",
        )
        assert history["records"][0]["date"] == expected_date


class TestIsoFormat:
    """ISO formatting helpers."""

    def test_isoformat_utc_is_aware(self):
        text = isoformat_utc(datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
        assert text.endswith("+00:00")

    def test_isoformat_utc_naive_becomes_utc(self):
        text = isoformat_utc(datetime(2026, 7, 30, 12, 0))
        assert text.endswith("+00:00")

    def test_display_date_handles_naive_as_utc(self):
        assert display_date(datetime(2026, 7, 30, 12, 0)) == "2026-07-30"
