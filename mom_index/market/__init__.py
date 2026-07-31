"""Market snapshot validation/import/load with honest degraded states.

This module owns the local boundary for market context snapshots.  It validates
configured sectors, reference symbol/name, provider label, timezone-aware
as-of/import timestamps, and any non-empty subset of 1d/5d/20d window returns.

Invalid or missing snapshots degrade to an unavailable context instead of
breaking dashboard construction.  This module intentionally does not import any
analysis or scoring code.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mom_index.config import MARKET_REFERENCES, SECTOR_KEYS

_MARKET_RETURN_WINDOWS = ("1d", "5d", "20d")


class MarketSnapshotError(ValueError):
    """Raised when a market snapshot violates its contract."""


class MarketSnapshotNotFoundError(MarketSnapshotError):
    """Raised when a market snapshot file does not exist."""


class _MarketSnapshotValidationError(MarketSnapshotError):
    """Internal validation failure carrying a deterministic reason code."""


class _SnapshotReason:
    """Stable reason codes for unavailable market context."""

    FILE_NOT_FOUND = "SNAPSHOT_FILE_NOT_FOUND"
    INVALID_JSON = "SNAPSHOT_INVALID_JSON"
    INVALID_SCHEMA_VERSION = "SNAPSHOT_INVALID_SCHEMA_VERSION"
    INVALID_PROVIDER = "SNAPSHOT_INVALID_PROVIDER"
    INVALID_IMPORTED_AT = "SNAPSHOT_INVALID_IMPORTED_AT"
    MISSING_SECTORS = "SNAPSHOT_MISSING_SECTORS"
    UNEXPECTED_SECTORS = "SNAPSHOT_UNEXPECTED_SECTORS"
    INVALID_SECTOR = "SNAPSHOT_INVALID_SECTOR"
    INVALID_SYMBOL = "SNAPSHOT_INVALID_SYMBOL"
    INVALID_NAME = "SNAPSHOT_INVALID_NAME"
    INVALID_AS_OF = "SNAPSHOT_INVALID_AS_OF"
    INVALID_RETURNS = "SNAPSHOT_INVALID_RETURNS"
    EMPTY_RETURNS = "SNAPSHOT_EMPTY_RETURNS"


def _iso(value: datetime) -> str:
    """Render a timezone-aware datetime in ISO 8601 UTC form."""

    return value.astimezone(timezone.utc).isoformat()


def _parse_timestamp(value: Any, path: str) -> datetime:
    """Parse a timezone-aware ISO timestamp or raise a deterministic error."""

    if not isinstance(value, str):
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_IMPORTED_AT,
            f"{path} must be an ISO timestamp string",
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_IMPORTED_AT,
            f"{path} is not a valid ISO timestamp: {value}",
        ) from exc
    if parsed.tzinfo is None:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_IMPORTED_AT,
            f"{path} must be timezone-aware: {value}",
        )
    return parsed


def _validate_sector(sector: str, value: Any) -> dict[str, Any]:
    """Validate and normalize a single sector snapshot."""

    if not isinstance(value, dict):
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_SECTOR,
            f"sectors.{sector} must be an object",
        )
    reference = MARKET_REFERENCES[sector]
    symbol = value.get("symbol")
    name = value.get("name")
    if symbol != reference["symbol"]:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_SYMBOL,
            f"sectors.{sector}.symbol must be {reference['symbol']!r}, got {symbol!r}",
        )
    if name != reference["name"]:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_NAME,
            f"sectors.{sector}.name must be {reference['name']!r}, got {name!r}",
        )
    as_of = _parse_timestamp(
        value.get("as_of"),
        f"sectors.{sector}.as_of",
    )
    raw_returns = value.get("returns")
    if not isinstance(raw_returns, dict):
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_RETURNS,
            f"sectors.{sector}.returns must be an object",
        )
    returns: dict[str, float] = {}
    for window in _MARKET_RETURN_WINDOWS:
        if window not in raw_returns:
            continue
        raw = raw_returns[window]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise _MarketSnapshotValidationError(
                _SnapshotReason.INVALID_RETURNS,
                f"sectors.{sector}.returns.{window} must be a number",
            )
        number = float(raw)
        if not math.isfinite(number):
            raise _MarketSnapshotValidationError(
                _SnapshotReason.INVALID_RETURNS,
                f"sectors.{sector}.returns.{window} must be finite",
            )
        returns[window] = number
    if not returns:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.EMPTY_RETURNS,
            f"sectors.{sector}.returns must contain at least one window",
        )
    return {
        "symbol": symbol,
        "name": name,
        "as_of": as_of,
        "returns": returns,
    }


def validate_snapshot(value: Any) -> dict[str, Any]:
    """Validate and normalize a market snapshot dictionary.

    Raises ``MarketSnapshotError`` when the snapshot is missing required fields,
    uses unexpected sector keys, references the wrong symbol/name, contains
    timezone-naive timestamps, or provides invalid window returns.

    The returned dictionary contains timezone-aware ``datetime`` objects for
    ``imported_at`` and each sector's ``as_of``.  Callers that need plain JSON
    can render those datetimes with ``isoformat_utc`` from ``mom_index.config``.
    """

    if not isinstance(value, dict):
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_SCHEMA_VERSION,
            "snapshot must be an object",
        )
    schema_version = value.get("schema_version")
    if schema_version != 1:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_SCHEMA_VERSION,
            f"schema_version must be 1, got {schema_version!r}",
        )
    provider = value.get("provider")
    if not isinstance(provider, str) or not provider.strip():
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_PROVIDER,
            "provider must be a non-empty string",
        )
    imported_at = _parse_timestamp(value.get("imported_at"), "imported_at")
    raw_sectors = value.get("sectors")
    if not isinstance(raw_sectors, dict):
        raise _MarketSnapshotValidationError(
            _SnapshotReason.MISSING_SECTORS,
            "sectors must be an object",
        )
    missing = sorted(set(SECTOR_KEYS) - set(raw_sectors))
    if missing:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.MISSING_SECTORS,
            f"missing sectors: {', '.join(missing)}",
        )
    extra = sorted(set(raw_sectors) - set(SECTOR_KEYS))
    if extra:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.UNEXPECTED_SECTORS,
            f"unexpected sectors: {', '.join(extra)}",
        )
    sectors = {
        sector: _validate_sector(sector, raw_sectors[sector])
        for sector in SECTOR_KEYS
    }
    return {
        "schema_version": 1,
        "provider": provider.strip(),
        "imported_at": imported_at,
        "sectors": sectors,
    }


def load_snapshot(path: Path) -> dict[str, Any]:
    """Load and strictly validate a market snapshot from a JSON file.

    Raises ``MarketSnapshotNotFoundError`` when the file is missing and
    ``MarketSnapshotError`` for JSON or contract violations.
    """

    if not isinstance(path, Path):
        path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise MarketSnapshotNotFoundError(
            f"snapshot file not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise _MarketSnapshotValidationError(
            _SnapshotReason.INVALID_JSON,
            f"invalid JSON in snapshot file: {exc}",
        ) from exc
    return validate_snapshot(value)


def unavailable_snapshot(*errors: str) -> dict[str, Any]:
    """Return an unavailable market context with optional human-readable errors."""

    return {
        "status": "unavailable",
        "provider": None,
        "imported_at": None,
        "errors": [str(error) for error in errors],
        "sectors": {sector: None for sector in SECTOR_KEYS},
    }


def import_snapshot(path: Path) -> dict[str, Any]:
    """Load a market snapshot or return an unavailable context on failure.

    This is the fail-closed entry point for CLI wiring.  A missing file,
    malformed JSON, or contract violation never propagates as an exception;
    instead an unavailable context is returned with a stable reason code and a
    human-readable message so the dashboard can still be built.
    """

    try:
        snapshot = load_snapshot(path)
    except MarketSnapshotError as exc:
        return unavailable_snapshot(str(exc))
    return {
        "status": "available",
        "provider": snapshot["provider"],
        "imported_at": _iso(snapshot["imported_at"]),
        "errors": [],
        "sectors": {
            sector: {
                "symbol": data["symbol"],
                "name": data["name"],
                "as_of": _iso(data["as_of"]),
                "returns": dict(data["returns"]),
            }
            for sector, data in snapshot["sectors"].items()
        },
    }


def degraded_snapshot(snapshot: dict[str, Any], *errors: str) -> dict[str, Any]:
    """Mark a previously validated snapshot as degraded with explicit errors."""

    available = sum(
        1
        for sector in SECTOR_KEYS
        if isinstance(snapshot.get("sectors", {}).get(sector), dict)
    )
    status = "degraded" if available > 0 else "unavailable"
    return {
        "status": status,
        "provider": snapshot.get("provider"),
        "imported_at": snapshot.get("imported_at"),
        "errors": [str(error) for error in errors],
        "sectors": snapshot.get("sectors", {sector: None for sector in SECTOR_KEYS}),
    }
