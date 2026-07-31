"""JSON Schema validation plus public-data privacy invariants."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from mom_index.config import (
    DISPLAY_TIMEZONE,
    MARKET_REFERENCES,
    PUBLIC_SCHEMA_VERSION,
    SCHEMA_PATH,
    SECTOR_KEYS,
)

_BANNED_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "author",
    "author_id",
    "author_followers",
    "avatar",
    "browser_profile",
    "client_secret",
    "cookie",
    "cookies",
    "follower_count",
    "followers",
    "following",
    "following_count",
    "display_name",
    "nickname",
    "password",
    "profile",
    "profile_url",
    "raw_records",
    "refresh_token",
    "secret",
    "secret_key",
    "session",
    "session_id",
    "session_token",
    "username",
    "user_id",
    "token",
}
_SECRET_VALUE = re.compile(
    r"(?i)(?:"
    r"(authorization|cookie|password|secret|token|api[_-]?key)\s*[:=]\s*[^\s*][^\s]*"
    r"|bearer\s+[A-Za-z0-9._-]{8,}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|gh[ps]_[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r")"
)


class PayloadValidationError(ValueError):
    """Raised when a public payload violates schema or privacy constraints."""


def _validation_view(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return a strict v3 validation view without mutating legacy v2 input.

    The public data branch can temporarily lag one schema revision behind the
    code branch during deployment.  Schema v2 is additive-upgraded in memory so
    it still passes through the complete built-in and JSON Schema v3 validators.
    """

    version = payload.get("schema_version")
    if version == PUBLIC_SCHEMA_VERSION:
        return payload, False
    if version != 2:
        raise PayloadValidationError(
            f"Unsupported schema_version: expected 2 or {PUBLIC_SCHEMA_VERSION}"
        )

    upgraded = deepcopy(payload)
    upgraded["schema_version"] = PUBLIC_SCHEMA_VERSION

    methodology = upgraded.get("methodology")
    if isinstance(methodology, dict):
        methodology.setdefault("confidence_model_version", "legacy-v2")

    latest = upgraded.get("latest")
    latest_sectors = latest.get("sectors") if isinstance(latest, dict) else None
    if isinstance(latest_sectors, dict):
        for sector_value in latest_sectors.values():
            if isinstance(sector_value, dict):
                sector_value.setdefault("sample_quality", None)

    upgraded["market_context"] = {
        "status": "unavailable",
        "provider": None,
        "imported_at": None,
        "errors": ["Legacy schema v2 payload has no market context."],
        "sectors": {sector: None for sector in SECTOR_KEYS},
    }
    return upgraded, True


def _timezone_aware(value: Any, path: str) -> None:
    if not isinstance(value, str):
        raise PayloadValidationError(f"{path} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PayloadValidationError(f"{path} is not a valid ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise PayloadValidationError(f"{path} must include a timezone")


def _walk_public(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key))
            normalized_key = re.sub(r"[^a-z0-9]+", "_", key_text.lower()).strip("_")
            if normalized_key in _BANNED_KEYS:
                raise PayloadValidationError(f"Private field is not allowed at {path}.{key}")
            _walk_public(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_public(nested, f"{path}[{index}]")
    elif isinstance(value, str) and _SECRET_VALUE.search(value):
        raise PayloadValidationError(f"Secret-like value is not allowed at {path}")


def _built_in_validate(payload: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "generated_at",
        "display_timezone",
        "sources",
        "freshness",
        "warnings",
        "methodology",
        "latest",
        "sector_history",
        "market_context",
        "record_count",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise PayloadValidationError(f"Missing top-level fields: {', '.join(missing)}")
    if payload["schema_version"] != PUBLIC_SCHEMA_VERSION:
        raise PayloadValidationError(
            f"schema_version must be {PUBLIC_SCHEMA_VERSION}"
        )
    if payload["display_timezone"] != DISPLAY_TIMEZONE:
        raise PayloadValidationError(
            f"display_timezone must be {DISPLAY_TIMEZONE}"
        )
    _timezone_aware(payload["generated_at"], "$.generated_at")
    if not isinstance(payload["sources"], list):
        raise PayloadValidationError("sources must be an array")
    for index, source in enumerate(payload["sources"]):
        if not isinstance(source, dict):
            raise PayloadValidationError(f"sources[{index}] must be an object")
        if source.get("mode") not in {
            "live",
            "imported",
            "simulated",
            "unavailable",
        }:
            raise PayloadValidationError(f"sources[{index}].mode is invalid")
        collected_at = source.get("collected_at")
        if source.get("mode") == "unavailable" and collected_at is not None:
            raise PayloadValidationError(
                f"sources[{index}].collected_at must be null when unavailable"
            )
        if collected_at is not None:
            _timezone_aware(collected_at, f"$.sources[{index}].collected_at")
    freshness = payload["freshness"]
    if not isinstance(freshness, dict) or not isinstance(
        freshness.get("is_stale"), bool
    ):
        raise PayloadValidationError("freshness is invalid")
    if freshness.get("last_success_at") is not None:
        _timezone_aware(freshness["last_success_at"], "$.freshness.last_success_at")
    sector_history = payload["sector_history"]
    if not isinstance(sector_history, dict) or set(sector_history) != set(
        SECTOR_KEYS
    ):
        raise PayloadValidationError(
            "sector_history must contain exactly the four configured sectors"
        )
    for sector, points in sector_history.items():
        if not isinstance(points, list):
            raise PayloadValidationError(f"sector_history.{sector} must be an array")
        for index, point in enumerate(points):
            if not isinstance(point, dict):
                raise PayloadValidationError(
                    f"sector_history.{sector}[{index}] must be an object"
                )
            if point.get("source_mode") not in {"live", "imported", "simulated"}:
                raise PayloadValidationError(
                    f"sector_history.{sector}[{index}].source_mode is invalid"
                )
    latest = payload["latest"]
    if latest is not None:
        latest_sectors = latest.get("sectors") if isinstance(latest, dict) else None
        if not isinstance(latest_sectors, dict) or set(latest_sectors) != set(
            SECTOR_KEYS
        ):
            raise PayloadValidationError(
                "latest must contain exactly the four configured sectors"
            )
        for sector, sector_value in latest_sectors.items():
            if not isinstance(sector_value, dict) or "sample_quality" not in sector_value:
                raise PayloadValidationError(
                    f"latest.sectors.{sector}.sample_quality must be present"
                )
            quality = sector_value["sample_quality"]
            if quality is not None and (
                not isinstance(quality, dict)
                or quality.get("confidence") not in {"high", "medium", "low"}
            ):
                raise PayloadValidationError(
                    f"latest.sectors.{sector}.sample_quality is invalid"
                )
    methodology = payload["methodology"]
    if (
        not isinstance(methodology, dict)
        or not isinstance(methodology.get("confidence_model_version"), str)
        or not methodology["confidence_model_version"]
    ):
        raise PayloadValidationError("methodology.confidence_model_version is invalid")
    market_context = payload["market_context"]
    if not isinstance(market_context, dict):
        raise PayloadValidationError("market_context must be an object")
    if market_context.get("status") not in {
        "available",
        "degraded",
        "unavailable",
    }:
        raise PayloadValidationError("market_context.status is invalid")
    market_sectors = market_context.get("sectors")
    if not isinstance(market_sectors, dict) or set(market_sectors) != set(SECTOR_KEYS):
        raise PayloadValidationError(
            "market_context.sectors must contain exactly the four configured sectors"
        )
    if market_context.get("status") == "unavailable":
        if (
            market_context.get("provider") is not None
            or market_context.get("imported_at") is not None
        ):
            raise PayloadValidationError(
                "unavailable market_context cannot claim provider or imported_at"
            )
        if any(value is not None for value in market_sectors.values()):
            raise PayloadValidationError(
                "unavailable market_context cannot carry sector observations"
            )
    else:
        if not isinstance(market_context.get("provider"), str):
            raise PayloadValidationError("market_context.provider is invalid")
        _timezone_aware(
            market_context.get("imported_at"),
            "$.market_context.imported_at",
        )
        available_count = sum(value is not None for value in market_sectors.values())
        if (
            market_context["status"] == "available"
            and available_count != len(SECTOR_KEYS)
        ):
            raise PayloadValidationError(
                "available market_context must contain all sector observations"
            )
        if market_context["status"] == "degraded" and available_count == 0:
            raise PayloadValidationError(
                "degraded market_context must contain at least one sector observation"
            )
    for sector, sector_value in market_sectors.items():
        if sector_value is None:
            continue
        if not isinstance(sector_value, dict):
            raise PayloadValidationError(
                f"market_context.sectors.{sector} must be an object or null"
            )
        reference = MARKET_REFERENCES[sector]
        if (
            sector_value.get("symbol") != reference["symbol"]
            or sector_value.get("name") != reference["name"]
        ):
            raise PayloadValidationError(
                f"market_context.sectors.{sector} reference is invalid"
            )
        _timezone_aware(
            sector_value.get("as_of"),
            f"$.market_context.sectors.{sector}.as_of",
        )
    if (
        not isinstance(payload["record_count"], int)
        or isinstance(payload["record_count"], bool)
        or payload["record_count"] < 0
    ):
        raise PayloadValidationError("record_count must be a non-negative integer")
    if payload["record_count"] == 0 and latest is not None:
        raise PayloadValidationError("latest must be null when record_count is zero")


def validate_payload(
    payload: dict[str, Any],
    *,
    schema_path: Path = SCHEMA_PATH,
) -> str:
    """Validate and return the schema engine used."""

    validation_payload, legacy_v2 = _validation_view(payload)
    _built_in_validate(validation_payload)
    _walk_public(payload)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        suffix = " with legacy schema v2 compatibility view" if legacy_v2 else ""
        return f"built-in bootstrap validator{suffix} (jsonschema not installed)"

    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(validation_payload),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        formatted = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
            for error in errors[:10]
        )
        raise PayloadValidationError(formatted)
    suffix = " with legacy schema v2 compatibility view" if legacy_v2 else ""
    return f"jsonschema Draft 2020-12{suffix}"


def validate_payload_file(path: Path, *, schema_path: Path = SCHEMA_PATH) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PayloadValidationError("Dashboard payload must be a JSON object")
    return validate_payload(value, schema_path=schema_path)
