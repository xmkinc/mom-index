"""JSON Schema validation plus public-data privacy invariants."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from mom_index.config import SCHEMA_PATH, SECTOR_KEYS

_BANNED_KEYS = {
    "author",
    "author_followers",
    "cookie",
    "cookies",
    "password",
    "raw_records",
}
_SECRET_VALUE = re.compile(
    r"(?i)(authorization|cookie|password|secret|token|api[_-]?key)\s*[:=]\s*[^\s*][^\s]*"
)


class PayloadValidationError(ValueError):
    """Raised when a public payload violates schema or privacy constraints."""


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
            if str(key).lower() in _BANNED_KEYS:
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
        "record_count",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise PayloadValidationError(f"Missing top-level fields: {', '.join(missing)}")
    if payload["schema_version"] != 2:
        raise PayloadValidationError("schema_version must be 2")
    if payload["display_timezone"] != "Asia/Shanghai":
        raise PayloadValidationError("display_timezone must be Asia/Shanghai")
    _timezone_aware(payload["generated_at"], "$.generated_at")
    if not isinstance(payload["sources"], list):
        raise PayloadValidationError("sources must be an array")
    for index, source in enumerate(payload["sources"]):
        if not isinstance(source, dict):
            raise PayloadValidationError(f"sources[{index}] must be an object")
        if source.get("mode") not in {"live", "simulated", "unavailable"}:
            raise PayloadValidationError(f"sources[{index}].mode is invalid")
        collected_at = source.get("collected_at")
        if source.get("mode") == "unavailable" and collected_at is not None:
            raise PayloadValidationError(f"sources[{index}].collected_at must be null when unavailable")
        if collected_at is not None:
            _timezone_aware(collected_at, f"$.sources[{index}].collected_at")
    freshness = payload["freshness"]
    if not isinstance(freshness, dict) or not isinstance(freshness.get("is_stale"), bool):
        raise PayloadValidationError("freshness is invalid")
    if freshness.get("last_success_at") is not None:
        _timezone_aware(freshness["last_success_at"], "$.freshness.last_success_at")
    if set(payload["sector_history"]) != set(SECTOR_KEYS):
        raise PayloadValidationError("sector_history must contain exactly the four configured sectors")
    latest = payload["latest"]
    if latest is not None:
        if not isinstance(latest, dict) or set(latest.get("sectors", {})) != set(SECTOR_KEYS):
            raise PayloadValidationError("latest must contain exactly the four configured sectors")
    if not isinstance(payload["record_count"], int) or payload["record_count"] < 0:
        raise PayloadValidationError("record_count must be a non-negative integer")
    if payload["record_count"] == 0 and latest is not None:
        raise PayloadValidationError("latest must be null when record_count is zero")


def validate_payload(
    payload: dict[str, Any],
    *,
    schema_path: Path = SCHEMA_PATH,
) -> str:
    """Validate and return the schema engine used."""

    _built_in_validate(payload)
    _walk_public(payload)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return "built-in bootstrap validator (jsonschema not installed)"

    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        formatted = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
            for error in errors[:10]
        )
        raise PayloadValidationError(formatted)
    return "jsonschema Draft 2020-12"


def validate_payload_file(path: Path, *, schema_path: Path = SCHEMA_PATH) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PayloadValidationError("Dashboard payload must be a JSON object")
    return validate_payload(value, schema_path=schema_path)
