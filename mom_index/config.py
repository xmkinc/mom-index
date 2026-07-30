"""Shared configuration for collection, storage, and public export."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
SCHEMA_PATH = PROJECT_ROOT / "schema" / "dashboard.schema.json"

DISPLAY_TIMEZONE = "Asia/Shanghai"
STALE_AFTER_HOURS = 12

SECTORS = {
    "nasdaq": {"name": "纳斯达克", "code": "of159941", "etf": "513100"},
    "gold": {"name": "黄金", "code": "of518880", "etf": "518880"},
    "cpo": {"name": "CPO通信", "code": "of515880", "etf": "515880"},
    "semiconductor": {"name": "半导体", "code": "of512480", "etf": "512480"},
}
SECTOR_NAMES = {key: value["name"] for key, value in SECTORS.items()}
SECTOR_KEYS = tuple(SECTORS)

SOURCE_LABELS = {
    "guba": "东方财富股吧",
    "xiaohongshu": "小红书",
}

METHODOLOGY = {
    "formula_version": "1.1",
    "weights": {
        "newbie_ratio": 0.40,
        "newbie_intensity": 0.25,
        "sentiment_extremity": 0.20,
        "purity": 0.15,
    },
}


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def isoformat_utc(value: datetime | None = None) -> str:
    """Render a timezone-aware timestamp in ISO 8601 form."""

    current = value or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def display_date(value: datetime) -> str:
    """Return the record date using the dashboard's Shanghai day boundary."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(DISPLAY_TIMEZONE)).date().isoformat()


def optional_proxy() -> str | None:
    """Return the explicitly configured collection proxy, if any."""

    value = os.environ.get("MOM_INDEX_PROXY", "").strip()
    return value or None
