"""Fail-closed local sanitized Xiaohongshu import boundary.

Accepts only stable public fields (``id``, ``title``, ``content``, ``url``,
``sector``, ``published_at``, ``collected_at``) from local JSON/JSONL files and
converts them into a ``SourceResult(mode="imported")``. Identity-, credential-,
and secret-bearing records abort the entire import (fail closed). Invalid
individual records are rejected explicitly with a per-record error rather than
silently stripped. Zero valid records yield an unavailable source.

This module never reads browser profiles, cookies, credentials, or network
resources, and is intentionally absent from the unattended public collector
registry. Public collectors and workflows are not modified here.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from mom_index.config import SECTOR_KEYS, SOURCE_LABELS, isoformat_utc

from . import SourceResult

SOURCE_ID = "xiaohongshu"

#: The only fields a sanitized import record may carry.
ALLOWED_FIELDS = frozenset(
    {
        "id",
        "title",
        "content",
        "url",
        "sector",
        "published_at",
        "collected_at",
    }
)

#: Identity, profile, session, and credential keys that abort the whole import.
#: Mirrors the public payload privacy scanner and is intentionally broad.
BANNED_IDENTITY_KEYS = frozenset(
    {
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
)

_SECRET_VALUE = re.compile(
    r"(?i)(?:"
    r"(authorization|cookie|password|secret|token|api[_-]?key)\s*[:=]\s*[^\s*][^\s]*"
    r"|bearer\s+[A-Za-z0-9._-]{8,}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|gh[ps]_[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r")"
)

_MAX_ID_LENGTH = 160
_MAX_TITLE_LENGTH = 300
_MAX_CONTENT_LENGTH = 20000
_VALID_SECTORS = frozenset(SECTOR_KEYS)
_VALID_XHS_HOSTS = frozenset({"xiaohongshu.com", "www.xiaohongshu.com"})


class XhsImportError(ValueError):
    """Raised when an import must fail closed (identity/credential/secret)."""


def _normalize_key(key: Any) -> str:
    """Normalize a key for banned-field comparison (camelCase/kebab-case aware)."""

    text = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _raise_on_private_data(value: Any, *, index: int) -> None:
    """Abort when any nested key or value resembles private credential data."""

    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            for key, nested in current.items():
                if _normalize_key(key) in BANNED_IDENTITY_KEYS:
                    raise XhsImportError(
                        f"record[{index}] contains a banned identity/credential "
                        "field; import aborted"
                    )
                pending.append(nested)
        elif isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, str) and _SECRET_VALUE.search(current):
            raise XhsImportError(
                f"record[{index}] contains a secret-like value; import aborted"
            )


def _valid_xhs_url(value: str) -> bool:
    """Return whether *value* is a safe HTTPS URL on an allowed XHS host."""

    if any(character.isspace() or ord(character) < 32 for character in value):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in _VALID_XHS_HOSTS
        and parsed.username is None
        and parsed.password is None
        and port is None
        and parsed.netloc == parsed.hostname
        and parsed.path.startswith("/")
    )


def _parse_timestamp(value: Any, *, field: str, record_id: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be an ISO timestamp string (record {record_id})"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field} is not a valid ISO timestamp (record {record_id})"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            f"{field} must include a timezone (record {record_id})"
        )
    return value


def _validate_record(record: Any, index: int) -> dict[str, Any]:
    """Validate one decoded record and return a normalized post dict.

    Raises ``XhsImportError`` for fail-closed conditions (banned identity keys
    or secret-like values). Raises ``ValueError`` for ordinary schema violations
    so the caller can reject the individual record explicitly and continue.
    """

    # Scan before ordinary schema checks so a malformed record cannot smuggle
    # private data past the fail-closed boundary.
    _raise_on_private_data(record, index=index)

    if not isinstance(record, dict):
        raise ValueError(f"record[{index}] must be a JSON object")

    raw_keys = set(record)
    unknown = raw_keys - ALLOWED_FIELDS
    if unknown:
        raise ValueError(
            f"record[{index}] has {len(unknown)} unknown field(s)"
        )

    required = (
        "id",
        "title",
        "content",
        "url",
        "sector",
        "published_at",
        "collected_at",
    )
    missing = [field for field in required if field not in record]
    if missing:
        raise ValueError(
            f"record[{index}] missing required fields: {sorted(missing)}"
        )

    for field in ("id", "title", "content", "url", "sector"):
        if not isinstance(record[field], str):
            raise ValueError(f"record[{index}].{field} must be a string")

    record_id = record["id"]
    if not record_id or len(record_id) > _MAX_ID_LENGTH:
        raise ValueError(
            f"record[{index}].id must be 1-{_MAX_ID_LENGTH} characters"
        )

    title = record["title"]
    if not title or len(title) > _MAX_TITLE_LENGTH:
        raise ValueError(
            f"record[{index}].title must be 1-{_MAX_TITLE_LENGTH} characters"
        )

    content = record["content"]
    if len(content) > _MAX_CONTENT_LENGTH:
        raise ValueError(
            f"record[{index}].content exceeds {_MAX_CONTENT_LENGTH} characters"
        )

    url = record["url"]
    if not _valid_xhs_url(url):
        raise ValueError(
            f"record[{index}].url must be an HTTPS xiaohongshu.com URL"
        )

    sector = record["sector"]
    if sector not in _VALID_SECTORS:
        raise ValueError(
            f"record[{index}].sector must be one of {sorted(_VALID_SECTORS)}"
        )

    published_at = record["published_at"]
    if published_at is not None:
        published_at = _parse_timestamp(
            published_at, field="published_at", record_id=record_id
        )

    collected_at = _parse_timestamp(
        record["collected_at"], field="collected_at", record_id=record_id
    )

    return {
        "id": record_id,
        "title": title,
        "content": content,
        "url": url,
        "platform": "xiaohongshu",
        "sector": sector,
        "published_at": published_at,
        "collected_at": collected_at,
    }


def _decode_json(raw_text: str) -> list[Any]:
    """Decode a JSON document into a flat list of candidate records."""

    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if not data:
            raise ValueError("import object is empty")
        if set(data.keys()) <= set(SECTOR_KEYS):
            records: list[Any] = []
            for sector, items in data.items():
                if not isinstance(items, list):
                    raise ValueError(f"sectorMap.{sector} must be an array")
                for item in items:
                    if isinstance(item, dict) and item.get("sector") != sector:
                        raise ValueError(
                            f"sectorMap.{sector} record has mismatched sector field"
                        )
                    records.append(item)
            return records
        raise ValueError("import object keys must be sector names")
    raise ValueError("import JSON must be an array or a sector map")


def _decode_jsonl(raw_text: str) -> list[Any]:
    """Decode newline-delimited JSON into a list of candidate records."""

    records: list[Any] = []
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ValueError(f"JSONL line {line_no} is not valid JSON: {exc}") from exc
        records.append(item)
    if not records:
        raise ValueError("JSONL input contained no records")
    return records


def _decode_records(raw_text: str, path: Path) -> list[Any]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _decode_jsonl(raw_text)
    return _decode_json(raw_text)


def import_xhs_file(
    path: str | Path,
    *,
    source_id: str = SOURCE_ID,
) -> SourceResult:
    """Import a local sanitized Xiaohongshu JSON/JSONL file.

    Returns a ``SourceResult`` with ``mode="imported"`` on success, or
    ``mode="unavailable"`` when the file is missing, unparseable, contains a
    fail-closed identity/credential/secret field, or yields zero valid records.
    """

    file_path = Path(path)
    if not file_path.is_file():
        return SourceResult.unavailable(source_id, "import file not found")

    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return SourceResult.unavailable(
            source_id, f"cannot read import file ({type(exc).__name__})"
        )

    try:
        records = _decode_records(raw_text, file_path)
    except ValueError as exc:
        return SourceResult.unavailable(source_id, str(exc))

    posts: dict[str, list[dict[str, Any]]] = {sector: [] for sector in SECTOR_KEYS}
    errors: list[str] = []
    for index, record in enumerate(records):
        try:
            post = _validate_record(record, index)
        except XhsImportError as exc:
            # Fail closed: abort the entire import on identity/secret exposure.
            return SourceResult.unavailable(source_id, str(exc))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        posts[post["sector"]].append(post)

    valid_count = sum(len(items) for items in posts.values())
    if valid_count == 0:
        if not errors:
            errors.append("import contained zero valid records")
        return SourceResult(
            source_id=source_id,
            label=SOURCE_LABELS.get(source_id, source_id),
            mode="unavailable",
            posts=posts,
            errors=errors,
        )

    return SourceResult(
        source_id=source_id,
        label=SOURCE_LABELS.get(source_id, source_id),
        mode="imported",
        posts=posts,
        collected_at=isoformat_utc(),
        errors=errors,
    )


__all__ = ["XhsImportError", "import_xhs_file"]
