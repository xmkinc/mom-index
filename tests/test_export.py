"""Tests for public payload export, schema validation, and privacy."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from mom_index.collectors import SourceResult
from mom_index.config import MARKET_REFERENCES, PROJECT_ROOT
from mom_index.export import _public_url, build_payload
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


def _imported_result() -> SourceResult:
    return SourceResult(
        source_id="xiaohongshu",
        label="小红书",
        mode="imported",
        posts={"nasdaq": [{"id": "xhs-1", "title": "怎么办"}]},
        collected_at="2026-07-30T12:00:00+00:00",
    )


def _gates() -> list[dict]:
    return [
        {"code": "sample_size_below_30", "level": "low", "passed": True, "actual": 40, "threshold": 30, "comparator": "gte"},
        {"code": "sample_size_below_60", "level": "high", "passed": False, "actual": 40, "threshold": 60, "comparator": "gte"},
        {"code": "title_only_ratio_above_0_8", "level": "low", "passed": True, "actual": 0.5, "threshold": 0.8, "comparator": "lte"},
    ]


def _sample_quality() -> dict:
    return {
        "model_version": "1.0",
        "confidence": "medium",
        "valid_sample_size": 40,
        "title_only_ratio": 0.5,
        "platform_counts": {"guba": 30, "xiaohongshu": 10},
        "classifier_evidence_coverage": 0.45,
        "known_in_window_ratio": 0.7,
        "unknown_time_ratio": 0.1,
        "window_hours": 72,
        "reason_codes": ["sample_size_below_60"],
        "gates": _gates(),
    }


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
        "nasdaq": {"index": 10.0, "interpretation": "test", "details": _valid_details(), "top_newbie_posts": [], "sample_quality": _sample_quality()},
        "gold": {"index": 20.0, "interpretation": "test", "details": _valid_details(), "top_newbie_posts": [], "sample_quality": _sample_quality()},
        "cpo": {"index": 30.0, "interpretation": "test", "details": _valid_details(), "top_newbie_posts": [], "sample_quality": _sample_quality()},
        "semiconductor": {"index": 40.0, "interpretation": "test", "details": _valid_details(), "top_newbie_posts": [], "sample_quality": _sample_quality()},
    }
    return merge_success(history, sectors, collected_at="2026-07-30T12:00:00+00:00", source_mode="live")


def _market_snapshot() -> dict:
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


class TestSchemaValidation:
    """Exported payloads must validate against schema v3."""

    def test_live_payload_validates(self):
        payload = build_payload(_history(), [_live_result()])
        engine = validate_payload(payload)
        assert "jsonschema" in engine
        assert payload["schema_version"] == 3
        assert payload["market_context"]["status"] == "unavailable"
        assert payload["latest"]["sectors"]["nasdaq"]["sample_quality"]["confidence"] == "medium"

    def test_unavailable_payload_validates(self):
        payload = build_payload(empty_history(), [_unavailable_result()])
        engine = validate_payload(payload)
        assert "jsonschema" in engine
        assert payload["freshness"]["is_stale"] is True

    def test_legacy_v2_payload_validates_without_mutation(self):
        payload = build_payload(_history(), [_live_result()])
        payload["schema_version"] = 2
        payload.pop("market_context")
        payload["methodology"].pop("confidence_model_version")
        for sector_value in payload["latest"]["sectors"].values():
            sector_value.pop("sample_quality")
        original = deepcopy(payload)

        engine = validate_payload(payload)

        assert "legacy schema v2 compatibility view" in engine
        assert payload == original

    def test_unknown_schema_version_is_rejected(self):
        payload = build_payload(_history(), [_live_result()])
        payload["schema_version"] = 99

        with pytest.raises(PayloadValidationError, match="Unsupported schema_version"):
            validate_payload(payload)

    def test_legacy_v2_payload_still_enforces_privacy(self):
        payload = build_payload(_history(), [_live_result()])
        payload["schema_version"] = 2
        payload.pop("market_context")
        payload["methodology"].pop("confidence_model_version")
        for sector_value in payload["latest"]["sectors"].values():
            sector_value.pop("sample_quality")
        payload["warnings"].append("api_key=secret123")

        with pytest.raises(PayloadValidationError, match="Secret-like"):
            validate_payload(payload)

    def test_simulated_payload_has_warning(self):
        payload = build_payload(empty_history(), [_simulated_result()])
        engine = validate_payload(payload)
        assert "jsonschema" in engine
        assert any("simulated" in w.lower() for w in payload["warnings"])

    def test_imported_modes_validate_in_source_and_history(self):
        history = merge_success(
            empty_history(),
            {
                sector: {
                    "index": 10.0,
                    "interpretation": "test",
                    "details": _valid_details(),
                    "top_newbie_posts": [],
                }
                for sector in MARKET_REFERENCES
            },
            collected_at="2026-07-30T12:00:00+00:00",
            source_mode="imported",
        )
        payload = build_payload(history, [_live_result(), _imported_result()])
        validate_payload(payload)
        assert payload["sources"][1]["mode"] == "imported"
        assert payload["sector_history"]["nasdaq"][0]["source_mode"] == "imported"
        assert any("imported" in warning for warning in payload["warnings"])

    def test_v2_history_exports_additively_with_null_quality(self):
        legacy = _history()
        legacy["schema_version"] = 2
        for sector_value in legacy["records"][0]["sectors"].values():
            sector_value.pop("sample_quality", None)
        payload = build_payload(legacy, [_live_result()])
        validate_payload(payload)
        assert payload["schema_version"] == 3
        assert payload["latest"]["sectors"]["nasdaq"]["sample_quality"] is None

    def test_market_snapshot_normalizes_and_validates(self):
        payload = build_payload(
            _history(),
            [_live_result()],
            market_context=_market_snapshot(),
        )
        validate_payload(payload)
        assert payload["market_context"]["status"] == "available"
        assert payload["market_context"]["sectors"]["gold"]["returns"]["20d"] == 3.75

    def test_invalid_market_snapshot_degrades_without_breaking_payload(self):
        snapshot = _market_snapshot()
        snapshot["sectors"]["nasdaq"]["symbol"] = "wrong-symbol"
        snapshot["sectors"]["gold"]["as_of"] = "not-a-timestamp"
        payload = build_payload(
            _history(),
            [_live_result()],
            market_context=snapshot,
        )
        validate_payload(payload)
        assert payload["market_context"]["status"] == "degraded"
        assert payload["market_context"]["sectors"]["nasdaq"] is None
        assert payload["market_context"]["sectors"]["gold"] is None

    def test_dashboard_schema_rejects_inconsistent_market_status(self):
        jsonschema = pytest.importorskip("jsonschema")
        schema = json.loads(
            (PROJECT_ROOT / "schema" / "dashboard.schema.json").read_text(
                encoding="utf-8"
            )
        )
        payload = build_payload(
            _history(),
            [_live_result()],
            market_context=_market_snapshot(),
        )
        payload["market_context"]["sectors"]["nasdaq"] = None
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(payload))
        assert errors

    def test_boundary_schemas_accept_sanitized_inputs(self):
        jsonschema = pytest.importorskip("jsonschema")
        checker = jsonschema.Draft202012Validator.FORMAT_CHECKER
        market_schema = json.loads(
            (PROJECT_ROOT / "schema" / "market_snapshot.schema.json").read_text(
                encoding="utf-8"
            )
        )
        xhs_schema = json.loads(
            (PROJECT_ROOT / "schema" / "xhs_import.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator.check_schema(market_schema)
        jsonschema.Draft202012Validator.check_schema(xhs_schema)
        jsonschema.Draft202012Validator(
            market_schema,
            format_checker=checker,
        ).validate(_market_snapshot())
        jsonschema.Draft202012Validator(
            xhs_schema,
            format_checker=checker,
        ).validate(
            [
                {
                    "id": "xhs-1",
                    "title": "现在入局还不晚吗",
                    "content": "",
                    "url": "https://www.xiaohongshu.com/explore/xhs-1",
                    "sector": "nasdaq",
                    "published_at": None,
                    "collected_at": "2026-07-30T12:00:00+00:00",
                }
            ]
        )

    def test_xhs_schema_rejects_identity_fields(self):
        jsonschema = pytest.importorskip("jsonschema")
        schema = json.loads(
            (PROJECT_ROOT / "schema" / "xhs_import.schema.json").read_text(
                encoding="utf-8"
            )
        )
        record = {
            "id": "xhs-1",
            "title": "怎么办",
            "content": "",
            "url": "https://www.xiaohongshu.com/explore/xhs-1",
            "sector": "nasdaq",
            "published_at": None,
            "collected_at": "2026-07-30T12:00:00+00:00",
            "author": "private identity",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate([record])


def _history_with_gates(gates_value) -> dict:
    history = _history()
    for sector_value in history["records"][0]["sectors"].values():
        sector_value["sample_quality"]["gates"] = gates_value
    return history


class TestQualityGatesExport:
    """Optional machine-readable gates: strict pass-through or clean omission."""

    def test_valid_gates_pass_through_and_validate(self):
        payload = build_payload(_history(), [_live_result()])
        engine = validate_payload(payload)
        assert "jsonschema" in engine
        quality = payload["latest"]["sectors"]["nasdaq"]["sample_quality"]
        assert quality["gates"] == _gates()

    def test_absent_gates_preserve_legacy_shape(self):
        history = _history()
        for sector_value in history["records"][0]["sectors"].values():
            sector_value["sample_quality"].pop("gates")
        payload = build_payload(history, [_live_result()])
        validate_payload(payload)
        quality = payload["latest"]["sectors"]["nasdaq"]["sample_quality"]
        assert quality is not None
        assert "gates" not in quality
        assert quality["confidence"] == "medium"

    @pytest.mark.parametrize(
        "malformed",
        [
            "not-a-list",
            {"code": "sample_size_below_30"},
            [{}],
            [{**_gates()[0], "extra": 1}],
            [{key: value for key, value in _gates()[0].items() if key != "passed"}],
            [{**_gates()[0], "code": ""}],
            [{**_gates()[0], "code": "x" * 81}],
            [{**_gates()[0], "code": 30}],
            [{**_gates()[0], "level": "medium"}],
            [{**_gates()[0], "passed": "yes"}],
            [{**_gates()[0], "actual": -1}],
            [{**_gates()[0], "actual": True}],
            [{**_gates()[0], "threshold": float("nan")}],
            [{**_gates()[0], "threshold": float("inf")}],
            [{**_gates()[0], "comparator": "eq"}],
            [_gates()[0]] * 13,
            _gates() + ["not-a-gate"],
        ],
    )
    def test_malformed_gates_are_omitted_without_discarding_quality(self, malformed):
        payload = build_payload(_history_with_gates(malformed), [_live_result()])
        validate_payload(payload)
        quality = payload["latest"]["sectors"]["nasdaq"]["sample_quality"]
        assert quality is not None
        assert "gates" not in quality
        assert quality["confidence"] == "medium"
        assert quality["reason_codes"] == ["sample_size_below_60"]

    def test_twelve_gates_are_the_maximum_passed_through(self):
        exactly_twelve = [_gates()[0]] * 12
        payload = build_payload(_history_with_gates(exactly_twelve), [_live_result()])
        validate_payload(payload)
        quality = payload["latest"]["sectors"]["nasdaq"]["sample_quality"]
        assert quality["gates"] == exactly_twelve

    def test_empty_gate_list_passes_through(self):
        payload = build_payload(_history_with_gates([]), [_live_result()])
        validate_payload(payload)
        quality = payload["latest"]["sectors"]["nasdaq"]["sample_quality"]
        assert quality["gates"] == []

    def test_dashboard_schema_rejects_malformed_gate_items(self):
        jsonschema = pytest.importorskip("jsonschema")
        schema = json.loads(
            (PROJECT_ROOT / "schema" / "dashboard.schema.json").read_text(
                encoding="utf-8"
            )
        )
        payload = build_payload(_history(), [_live_result()])
        for bad_gates in (
            [{**_gates()[0], "actual": -1}],
            [{**_gates()[0], "extra": 1}],
            [{**_gates()[0], "comparator": "eq"}],
            [_gates()[0]] * 13,
        ):
            broken = deepcopy(payload)
            broken["latest"]["sectors"]["nasdaq"]["sample_quality"]["gates"] = bad_gates
            errors = list(
                jsonschema.Draft202012Validator(schema).iter_errors(broken)
            )
            assert errors, f"schema accepted malformed gates: {bad_gates!r}"

    def test_computed_quality_gates_export_end_to_end(self):
        from mom_index.analysis.quality import compute_sample_quality

        computed = compute_sample_quality(
            [], [], datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
        )
        history = _history()
        for sector_value in history["records"][0]["sectors"].values():
            sector_value["sample_quality"] = computed
        payload = build_payload(history, [_live_result()])
        validate_payload(payload)
        quality = payload["latest"]["sectors"]["nasdaq"]["sample_quality"]
        assert quality["gates"] == computed["gates"]
        assert quality["reason_codes"] == computed["reason_codes"]
        assert quality["confidence"] == computed["confidence"]


class TestPrivacy:
    """Public payload must not leak private fields."""

    def test_no_author_fields(self):
        payload = build_payload(_history(), [_live_result()])
        with pytest.raises(PayloadValidationError, match="Private field"):
            polluted = dict(payload)
            polluted["author"] = "leak"
            validate_payload(polluted)

    @pytest.mark.parametrize(
        "identity_key",
        ["author_id", "authorId", "followers", "nickname", "profile_url", "user-id"],
    )
    def test_no_identity_fields(self, identity_key):
        payload = build_payload(_history(), [_live_result()])
        polluted = dict(payload)
        polluted[identity_key] = "leak"
        with pytest.raises(PayloadValidationError, match="Private field"):
            validate_payload(polluted)

    def test_no_secret_values(self):
        payload = build_payload(_history(), [_live_result()])
        with pytest.raises(PayloadValidationError, match="Secret-like"):
            polluted = dict(payload)
            polluted["warnings"] = ["api_key=secret123"]
            validate_payload(polluted)

    def test_source_errors_redact_bearer_tokens(self):
        source = SourceResult.unavailable(
            "guba",
            "request failed with Bearer abcdefghijklmnopqrstuvwxyz",
        )
        payload = build_payload(empty_history(), [source])
        validate_payload(payload)
        encoded = json.dumps(payload, ensure_ascii=False)
        assert "abcdefghijklmnopqrstuvwxyz" not in encoded
        assert "[redacted credential]" in encoded

    @pytest.mark.parametrize(
        "source_url",
        [
            "https://xiaohongshu.com/explore/bare-host",
            "https://www.xiaohongshu.com/explore/www-host",
        ],
    )
    def test_safe_xhs_source_hosts_are_public(self, source_url):
        assert _public_url(source_url) == source_url

    @pytest.mark.parametrize(
        "source_url",
        [
            "http://xiaohongshu.com/explore/insecure",
            "https://evil.xiaohongshu.com/explore/deceptive",
            "https://xiaohongshu.com.evil.example/explore/deceptive",
            "https://user:password@xiaohongshu.com/explore/credentials",
            "https://xiaohongshu.com:443/explore/port",
            "https://xiaohongshu.com/explore/has space",
            "javascript:alert(1)",
        ],
    )
    def test_unsafe_xhs_source_urls_are_rejected(self, source_url):
        assert _public_url(source_url) == ""


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
