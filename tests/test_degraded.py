"""Tests for degraded-state and unavailable-source contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mom_index import cli as cli_module
from mom_index.cli import build_dashboard, build_parser, collect_sources
from mom_index.collectors import SourceResult
from mom_index.collectors.guba import GubaCollector
from mom_index.config import MARKET_REFERENCES, SECTOR_KEYS
from mom_index.export import build_payload
from mom_index.storage import empty_history, load_history
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


def _xhs_record(sector: str) -> dict:
    return {
        "id": f"xhs-{sector}",
        "title": "小白怎么办，现在入局还来得及吗",
        "content": "第一次买，不会选股，求带。",
        "url": f"https://www.xiaohongshu.com/explore/{sector}",
        "sector": sector,
        "published_at": "2026-07-30T10:00:00+00:00",
        "collected_at": "2026-07-30T12:00:00+00:00",
    }


def _market_snapshot() -> dict:
    return {
        "schema_version": 1,
        "provider": "integration fixture",
        "imported_at": "2026-07-30T12:05:00+00:00",
        "sectors": {
            sector: {
                **reference,
                "as_of": "2026-07-30T12:00:00+00:00",
                "returns": {"1d": 1.0, "5d": -2.0, "20d": 3.0},
            }
            for sector, reference in MARKET_REFERENCES.items()
        },
    }


class TestLocalImportIntegration:
    """Local imports are explicit and remain outside the public defaults."""

    def test_parser_defaults_remain_public_guba_only(self):
        collect_args = build_parser().parse_args(["collect"])
        assert collect_args.sources == ["guba"]
        assert collect_args.xhs_import is None
        assert collect_args.allow_simulated is False

        all_args = build_parser().parse_args(["all"])
        assert all_args.sources == ["guba"]
        assert all_args.xhs_import is None
        assert all_args.market_import is None

    def test_xhs_import_updates_history_with_quality(self, tmp_path: Path):
        xhs_path = tmp_path / "xhs.json"
        xhs_path.write_text(
            json.dumps([_xhs_record(sector) for sector in SECTOR_KEYS]),
            encoding="utf-8",
        )
        data_dir = tmp_path / "data"
        results = collect_sources(
            source_names=[],
            allow_simulated=False,
            data_dir=data_dir,
            xhs_import_path=xhs_path,
        )
        assert [(result.source_id, result.mode) for result in results] == [
            ("xiaohongshu", "imported")
        ]

        payload, _ = build_dashboard(data_dir, data_dir / "dashboard_data.json")
        history = load_history(data_dir)
        assert payload["schema_version"] == 3
        assert history["records"][0]["source_mode"] == "imported"
        assert payload["sources"][1]["mode"] == "imported"
        for sector in SECTOR_KEYS:
            quality = payload["latest"]["sectors"][sector]["sample_quality"]
            assert quality["confidence"] == "low"
            assert quality["valid_sample_size"] == 1
            assert quality["platform_counts"] == {"xiaohongshu": 1}

    def test_market_import_is_independent_from_social_index(self, tmp_path: Path):
        xhs_path = tmp_path / "xhs.json"
        xhs_path.write_text(
            json.dumps([_xhs_record(sector) for sector in SECTOR_KEYS]),
            encoding="utf-8",
        )
        market_path = tmp_path / "market.json"
        market_path.write_text(json.dumps(_market_snapshot()), encoding="utf-8")
        data_dir = tmp_path / "data"
        collect_sources(
            source_names=[],
            allow_simulated=False,
            data_dir=data_dir,
            xhs_import_path=xhs_path,
        )

        without_market, _ = build_dashboard(
            data_dir,
            tmp_path / "without-market.json",
        )
        with_market, _ = build_dashboard(
            data_dir,
            tmp_path / "with-market.json",
            market_import_path=market_path,
        )
        without_indices = {
            sector: without_market["latest"]["sectors"][sector]["index"]
            for sector in SECTOR_KEYS
        }
        with_indices = {
            sector: with_market["latest"]["sectors"][sector]["index"]
            for sector in SECTOR_KEYS
        }
        assert with_indices == without_indices
        assert with_market["market_context"]["status"] == "available"
        assert with_market["market_context"]["provider"] == "integration fixture"

    def test_cli_import_flags_run_end_to_end(self, tmp_path: Path, monkeypatch):
        class UnavailableGuba:
            def collect(self):
                return SourceResult.unavailable("guba", "offline test fixture")

        monkeypatch.setattr(
            cli_module,
            "get_public_collectors",
            lambda: {"guba": UnavailableGuba},
        )
        xhs_path = tmp_path / "xhs.json"
        xhs_path.write_text(
            json.dumps([_xhs_record(sector) for sector in SECTOR_KEYS]),
            encoding="utf-8",
        )
        market_path = tmp_path / "market.json"
        market_path.write_text(json.dumps(_market_snapshot()), encoding="utf-8")
        data_dir = tmp_path / "data"
        output_path = data_dir / "dashboard_data.json"

        assert cli_module.main(
            [
                "collect",
                "--sources",
                "guba",
                "--xhs-import",
                str(xhs_path),
                "--out",
                str(data_dir),
            ]
        ) == 0
        assert cli_module.main(
            [
                "build",
                "--data",
                str(data_dir),
                "--market-import",
                str(market_path),
                "--out",
                str(output_path),
            ]
        ) == 0

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["sources"][0]["mode"] == "unavailable"
        assert payload["sources"][1]["mode"] == "imported"
        assert payload["market_context"]["status"] == "available"
        assert all(
            payload["latest"]["sectors"][sector]["sample_quality"] is not None
            for sector in SECTOR_KEYS
        )
