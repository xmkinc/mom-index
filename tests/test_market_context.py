"""Tests for market snapshot validation/import/load."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mom_index.config import MARKET_REFERENCES, SECTOR_KEYS
from mom_index.market import (
    MarketSnapshotError,
    MarketSnapshotNotFoundError,
    import_snapshot,
    load_snapshot,
    unavailable_snapshot,
    validate_snapshot,
)


def _valid_snapshot() -> dict:
    return {
        "schema_version": 1,
        "provider": "fixture provider",
        "imported_at": "2026-07-30T12:05:00+00:00",
        "sectors": {
            sector: {
                **reference,
                "as_of": "2026-07-30T07:00:00+00:00",
                "returns": {"1d": 1.25, "5d": -0.5, "20d": 3.75},
            }
            for sector, reference in MARKET_REFERENCES.items()
        },
    }


class TestValidateSnapshot:
    """Strict validation of market snapshot dictionaries."""

    def test_valid_snapshot_round_trips(self):
        snapshot = validate_snapshot(_valid_snapshot())
        assert snapshot["schema_version"] == 1
        assert snapshot["provider"] == "fixture provider"
        assert snapshot["imported_at"] == datetime(
            2026, 7, 30, 12, 5, tzinfo=timezone.utc
        )
        for sector in SECTOR_KEYS:
            assert snapshot["sectors"][sector]["symbol"] == MARKET_REFERENCES[sector]["symbol"]
            assert snapshot["sectors"][sector]["name"] == MARKET_REFERENCES[sector]["name"]
            assert snapshot["sectors"][sector]["returns"] == {
                "1d": 1.25,
                "5d": -0.5,
                "20d": 3.75,
            }

    def test_partial_returns_are_accepted(self):
        raw = _valid_snapshot()
        raw["sectors"]["nasdaq"]["returns"] = {"1d": 0.5}
        snapshot = validate_snapshot(raw)
        assert snapshot["sectors"]["nasdaq"]["returns"] == {"1d": 0.5}

    def test_missing_schema_version_rejected(self):
        raw = _valid_snapshot()
        raw.pop("schema_version")
        with pytest.raises(MarketSnapshotError, match="schema_version"):
            validate_snapshot(raw)

    def test_wrong_schema_version_rejected(self):
        raw = _valid_snapshot()
        raw["schema_version"] = 2
        with pytest.raises(MarketSnapshotError, match="schema_version"):
            validate_snapshot(raw)

    def test_empty_provider_rejected(self):
        raw = _valid_snapshot()
        raw["provider"] = "   "
        with pytest.raises(MarketSnapshotError, match="provider"):
            validate_snapshot(raw)

    def test_timezone_naive_imported_at_rejected(self):
        raw = _valid_snapshot()
        raw["imported_at"] = "2026-07-30T12:05:00"
        with pytest.raises(MarketSnapshotError, match="timezone"):
            validate_snapshot(raw)

    def test_invalid_imported_at_rejected(self):
        raw = _valid_snapshot()
        raw["imported_at"] = "not-a-date"
        with pytest.raises(MarketSnapshotError, match="ISO timestamp"):
            validate_snapshot(raw)

    def test_missing_sector_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"].pop("gold")
        with pytest.raises(MarketSnapshotError, match="missing sectors"):
            validate_snapshot(raw)

    def test_extra_sector_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["crypto"] = raw["sectors"]["gold"]
        with pytest.raises(MarketSnapshotError, match="unexpected sectors"):
            validate_snapshot(raw)

    def test_wrong_symbol_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["nasdaq"]["symbol"] = "999999"
        with pytest.raises(MarketSnapshotError, match="symbol"):
            validate_snapshot(raw)

    def test_wrong_name_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["nasdaq"]["name"] = "Wrong ETF"
        with pytest.raises(MarketSnapshotError, match="name"):
            validate_snapshot(raw)

    def test_timezone_naive_as_of_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["gold"]["as_of"] = "2026-07-30T07:00:00"
        with pytest.raises(MarketSnapshotError, match="timezone"):
            validate_snapshot(raw)

    def test_non_numeric_return_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["cpo"]["returns"]["1d"] = "boom"
        with pytest.raises(MarketSnapshotError, match="must be a number"):
            validate_snapshot(raw)

    def test_boolean_return_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["cpo"]["returns"]["1d"] = True
        with pytest.raises(MarketSnapshotError, match="must be a number"):
            validate_snapshot(raw)

    def test_infinite_return_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["cpo"]["returns"]["1d"] = float("inf")
        with pytest.raises(MarketSnapshotError, match="finite"):
            validate_snapshot(raw)

    def test_empty_returns_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["semiconductor"]["returns"] = {}
        with pytest.raises(MarketSnapshotError, match="at least one window"):
            validate_snapshot(raw)

    def test_non_object_returns_rejected(self):
        raw = _valid_snapshot()
        raw["sectors"]["semiconductor"]["returns"] = [1.0]
        with pytest.raises(MarketSnapshotError, match="must be an object"):
            validate_snapshot(raw)

    def test_unknown_return_window_ignored(self):
        raw = _valid_snapshot()
        raw["sectors"]["nasdaq"]["returns"]["30d"] = 5.0
        snapshot = validate_snapshot(raw)
        assert "30d" not in snapshot["sectors"]["nasdaq"]["returns"]


class TestLoadSnapshot:
    """Loading snapshots from files."""

    def test_load_valid_file(self, tmp_path: Path):
        path = tmp_path / "snapshot.json"
        path.write_text(json.dumps(_valid_snapshot()), encoding="utf-8")
        snapshot = load_snapshot(path)
        assert snapshot["provider"] == "fixture provider"

    def test_missing_file_raises_not_found(self, tmp_path: Path):
        path = tmp_path / "missing.json"
        with pytest.raises(MarketSnapshotNotFoundError):
            load_snapshot(path)

    def test_invalid_json_raises(self, tmp_path: Path):
        path = tmp_path / "snapshot.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(MarketSnapshotError, match="invalid JSON"):
            load_snapshot(path)

    def test_invalid_snapshot_raises(self, tmp_path: Path):
        path = tmp_path / "snapshot.json"
        raw = _valid_snapshot()
        raw["provider"] = ""
        path.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(MarketSnapshotError, match="provider"):
            load_snapshot(path)


class TestImportSnapshot:
    """Fail-closed import that degrades to unavailable on problems."""

    def test_import_valid_snapshot(self, tmp_path: Path):
        path = tmp_path / "snapshot.json"
        path.write_text(json.dumps(_valid_snapshot()), encoding="utf-8")
        context = import_snapshot(path)
        assert context["status"] == "available"
        assert context["provider"] == "fixture provider"
        assert context["imported_at"] == "2026-07-30T12:05:00+00:00"
        for sector in SECTOR_KEYS:
            assert context["sectors"][sector]["symbol"] == MARKET_REFERENCES[sector]["symbol"]
            assert context["sectors"][sector]["as_of"] == "2026-07-30T07:00:00+00:00"

    def test_import_missing_file_returns_unavailable(self, tmp_path: Path):
        context = import_snapshot(tmp_path / "missing.json")
        assert context["status"] == "unavailable"
        assert context["provider"] is None
        assert context["imported_at"] is None
        assert any("not found" in error for error in context["errors"])

    def test_import_invalid_snapshot_returns_unavailable(self, tmp_path: Path):
        path = tmp_path / "snapshot.json"
        raw = _valid_snapshot()
        raw["provider"] = ""
        path.write_text(json.dumps(raw), encoding="utf-8")
        context = import_snapshot(path)
        assert context["status"] == "unavailable"
        assert any("provider" in error for error in context["errors"])


class TestUnavailableSnapshot:
    """Unavailable context helper."""

    def test_unavailable_snapshot_has_all_sectors_null(self):
        context = unavailable_snapshot("market feed down")
        assert context["status"] == "unavailable"
        assert context["provider"] is None
        assert context["imported_at"] is None
        assert context["errors"] == ["market feed down"]
        assert all(context["sectors"][sector] is None for sector in SECTOR_KEYS)
