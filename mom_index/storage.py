"""Atomic storage for collection state and last-known-good index history."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from mom_index.collectors import SourceResult
from mom_index.config import (
    HISTORY_SCHEMA_VERSION,
    SECTOR_KEYS,
    SOURCE_MODE_PRECEDENCE,
    display_date,
)

HISTORY_FILENAME = "history.json"
COLLECTION_FILENAME = "collection.json"


def empty_history() -> dict[str, Any]:
    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "last_success_at": None,
        "records": [],
    }


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    """Write JSON atomically in the destination directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def load_history(data_dir: Path) -> dict[str, Any]:
    path = data_dir / HISTORY_FILENAME
    if not path.exists():
        return empty_history()
    value = read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("records"), list):
        raise ValueError(f"Invalid history file: {path}")
    version = value.get("schema_version", 2)
    if version not in {2, HISTORY_SCHEMA_VERSION}:
        raise ValueError(f"Unsupported history schema version {version!r}: {path}")
    return _upgrade_history(value)


def _upgrade_history(history: dict[str, Any]) -> dict[str, Any]:
    """Return a schema-v3 copy, adding nullable fields to legacy v2 records."""

    upgraded_records: list[dict[str, Any]] = []
    for raw_record in history.get("records", []):
        if not isinstance(raw_record, dict):
            continue
        record = dict(raw_record)
        source_mode = record.get("source_mode", "live")
        if source_mode not in SOURCE_MODE_PRECEDENCE:
            raise ValueError(
                f"Unsupported history source mode {source_mode!r}"
            )
        sectors = record.get("sectors")
        if isinstance(sectors, dict):
            upgraded_sectors: dict[str, Any] = {}
            for sector, raw_value in sectors.items():
                if isinstance(raw_value, dict):
                    value = dict(raw_value)
                    value.setdefault("sample_quality", None)
                    upgraded_sectors[str(sector)] = value
                else:
                    upgraded_sectors[str(sector)] = raw_value
            record["sectors"] = upgraded_sectors
        record["source_mode"] = source_mode
        upgraded_records.append(record)
    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "last_success_at": history.get("last_success_at"),
        "records": upgraded_records,
    }


def save_history(data_dir: Path, history: dict[str, Any]) -> None:
    write_json(data_dir / HISTORY_FILENAME, history)


def merge_success(
    history: dict[str, Any],
    sector_indices: dict[str, dict[str, Any]],
    *,
    collected_at: str,
    source_mode: str,
) -> dict[str, Any]:
    """Replace today's record only after a complete successful collection."""

    missing = [sector for sector in SECTOR_KEYS if sector not in sector_indices]
    if missing:
        raise ValueError(f"Cannot update LKG with missing sectors: {', '.join(missing)}")
    invalid_sectors = [
        sector
        for sector in SECTOR_KEYS
        if not isinstance(sector_indices.get(sector), dict)
    ]
    if invalid_sectors:
        raise ValueError(
            f"Cannot update LKG with invalid sectors: {', '.join(invalid_sectors)}"
        )
    if source_mode not in SOURCE_MODE_PRECEDENCE:
        raise ValueError(
            "Only live, imported, or explicit simulated results can update history"
        )

    timestamp = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("collected_at must be timezone-aware")
    record_date = display_date(timestamp)
    record = {
        "date": record_date,
        "timestamp": collected_at,
        "source_mode": source_mode,
        "sectors": {
            sector: {
                **sector_indices[sector],
                "sample_quality": sector_indices[sector].get("sample_quality"),
            }
            for sector in SECTOR_KEYS
        },
    }
    upgraded = _upgrade_history(history)
    records = [
        existing
        for existing in upgraded["records"]
        if existing.get("date") != record_date
    ]
    records.append(record)
    records.sort(
        key=lambda item: (
            str(item.get("date", "")),
            str(item.get("timestamp", "")),
        )
    )
    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "last_success_at": collected_at,
        "records": records,
    }


def dominant_source_mode(modes: list[str]) -> str:
    """Return the truthful caveat mode using simulated > imported > live."""

    if not modes:
        raise ValueError("At least one successful source mode is required")
    invalid = sorted(set(modes) - set(SOURCE_MODE_PRECEDENCE))
    if invalid:
        raise ValueError(f"Unsupported successful source modes: {', '.join(invalid)}")
    return max(modes, key=SOURCE_MODE_PRECEDENCE.__getitem__)


def save_collection(data_dir: Path, results: list[SourceResult]) -> Path:
    path = data_dir / COLLECTION_FILENAME
    write_json(
        path,
        {
            "collection_version": 1,
            "sources": [result.to_dict() for result in results],
        },
    )
    return path


def load_collection(data_dir: Path) -> list[SourceResult]:
    path = data_dir / COLLECTION_FILENAME
    if not path.exists():
        return []
    value = read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("sources"), list):
        raise ValueError(f"Invalid collection file: {path}")
    return [SourceResult.from_dict(item) for item in value["sources"] if isinstance(item, dict)]
