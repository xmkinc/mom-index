"""Atomic storage for collection state and last-known-good index history."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from mom_index.config import SECTOR_KEYS, display_date
from mom_index.collectors import SourceResult

HISTORY_FILENAME = "history.json"
COLLECTION_FILENAME = "collection.json"


def empty_history() -> dict[str, Any]:
    return {"schema_version": 2, "last_success_at": None, "records": []}


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
    value.setdefault("schema_version", 2)
    value.setdefault("last_success_at", None)
    return value


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
    if source_mode not in {"live", "simulated"}:
        raise ValueError("Only live or explicit simulated results can update history")

    timestamp = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("collected_at must be timezone-aware")
    record_date = display_date(timestamp)
    record = {
        "date": record_date,
        "timestamp": collected_at,
        "source_mode": source_mode,
        "sectors": {sector: sector_indices[sector] for sector in SECTOR_KEYS},
    }
    records = [
        existing
        for existing in history.get("records", [])
        if existing.get("date") != record_date
    ]
    records.append(record)
    records.sort(key=lambda item: (str(item.get("date", "")), str(item.get("timestamp", ""))))
    return {
        "schema_version": 2,
        "last_success_at": collected_at,
        "records": records,
    }


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
