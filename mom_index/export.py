"""Build the privacy-preserving public dashboard payload."""

from __future__ import annotations

import copy
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from mom_index.collectors import SourceResult
from mom_index.config import (
    DISPLAY_TIMEZONE,
    MARKET_REFERENCES,
    METHODOLOGY,
    PUBLIC_SCHEMA_VERSION,
    SECTOR_KEYS,
    STALE_AFTER_HOURS,
    isoformat_utc,
    utc_now,
)

_ALLOWED_POST_HOSTS = {
    "guba.eastmoney.com",
    "caifuhao.eastmoney.com",
    "xiaohongshu.com",
    "www.xiaohongshu.com",
}
_DETAIL_FIELDS = {
    "total_posts",
    "valid_posts",
    "spam_posts",
    "newbie_posts",
    "pure_newbie",
    "newbie_ratio",
    "avg_newbie_score",
    "avg_sentiment",
    "purity_signal",
    "activity",
    "mom_buy_index",
    "mom_sell_index",
    "buy_sell_ratio",
    "buy_count",
    "sell_count",
}
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(authorization|cookie|password|secret|token|api[_-]?key)\s*[:=]\s*\S+"
)
_SECRET_TOKEN = re.compile(
    r"(?i)(?:"
    r"bearer\s+[A-Za-z0-9._-]{8,}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|gh[ps]_[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r")"
)
_PROXY_CREDENTIAL = re.compile(r"(https?://)[^/@\s]+@", re.IGNORECASE)
_QUALITY_NUMBER_FIELDS = (
    "title_only_ratio",
    "classifier_evidence_coverage",
    "known_in_window_ratio",
    "unknown_time_ratio",
)
_MARKET_RETURN_WINDOWS = ("1d", "5d", "20d")


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _public_error(value: str) -> str:
    message = " ".join(str(value).split())
    message = _PROXY_CREDENTIAL.sub(r"\1***@", message)
    message = _SECRET_ASSIGNMENT.sub(r"\1=***", message)
    message = _SECRET_TOKEN.sub("[redacted credential]", message)
    return message[:240]


def _public_url(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    if any(character.isspace() or ord(character) < 32 for character in value):
        return ""
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return ""
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _ALLOWED_POST_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.netloc.lower() != parsed.hostname
        or not parsed.path.startswith("/")
    ):
        return ""
    return value


def _public_post(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(value.get("title", ""))[:60],
        "score": float(value.get("score", 0)),
        "level": str(value.get("level", "")),
        "reasoning": str(value.get("reasoning", ""))[:150],
        "intent": str(value.get("intent", "neutral")),
        "key_signals": [str(item)[:160] for item in value.get("key_signals", [])[:2]],
        "source_url": _public_url(value.get("source_url")),
    }


def _public_sample_quality(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    required = {
        "model_version",
        "confidence",
        "valid_sample_size",
        "title_only_ratio",
        "platform_counts",
        "classifier_evidence_coverage",
        "known_in_window_ratio",
        "unknown_time_ratio",
        "window_hours",
        "reason_codes",
    }
    if not required.issubset(value):
        return None
    model_version = value.get("model_version")
    if not isinstance(model_version, str) or not model_version:
        return None
    if value.get("confidence") not in {"high", "medium", "low"}:
        return None
    valid_sample_size = value.get("valid_sample_size")
    window_hours = value.get("window_hours")
    if (
        not isinstance(valid_sample_size, int)
        or isinstance(valid_sample_size, bool)
        or valid_sample_size < 0
        or not isinstance(window_hours, int)
        or isinstance(window_hours, bool)
        or window_hours < 1
    ):
        return None
    ratios: dict[str, float] = {}
    for field in _QUALITY_NUMBER_FIELDS:
        raw = value.get(field)
        if (
            not isinstance(raw, (int, float))
            or isinstance(raw, bool)
            or not 0 <= float(raw) <= 1
        ):
            return None
        ratios[field] = float(raw)
    raw_counts = value.get("platform_counts")
    if not isinstance(raw_counts, dict):
        return None
    platform_counts = {
        str(platform)[:40]: count
        for platform, count in raw_counts.items()
        if (
            isinstance(platform, str)
            and platform
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= 0
        )
    }
    raw_reasons = value.get("reason_codes")
    if not isinstance(raw_reasons, list) or not all(
        isinstance(reason, str) for reason in raw_reasons
    ):
        return None
    return {
        "model_version": model_version[:40],
        "confidence": value["confidence"],
        "valid_sample_size": valid_sample_size,
        **ratios,
        "platform_counts": platform_counts,
        "window_hours": window_hours,
        "reason_codes": list(dict.fromkeys(reason[:80] for reason in raw_reasons))[:20],
    }


def _public_sector(value: dict[str, Any]) -> dict[str, Any]:
    details = value.get("details", {})
    if not isinstance(details, dict):
        details = {}
    public_details = {
        key: details[key]
        for key in _DETAIL_FIELDS
        if key in details and (isinstance(details[key], (int, float)) or details[key] is None)
    }
    posts = value.get("top_newbie_posts", [])
    if not isinstance(posts, list):
        posts = []
    return {
        "index": float(value.get("index", 0)),
        "interpretation": str(value.get("interpretation", "")),
        "details": public_details,
        "top_newbie_posts": [
            _public_post(item)
            for item in posts[:5]
            if isinstance(item, dict)
        ],
        "sample_quality": _public_sample_quality(value.get("sample_quality")),
    }


def _source_status(result: SourceResult) -> dict[str, Any]:
    return {
        "id": result.source_id,
        "label": result.label,
        "mode": result.mode,
        "collected_at": result.collected_at,
        "post_count": result.post_count,
        "errors": [_public_error(error) for error in result.errors],
    }


def _ordered_sources(results: list[SourceResult]) -> list[dict[str, Any]]:
    by_id = {result.source_id: result for result in results}
    defaults = {
        "guba": SourceResult.unavailable("guba", "尚无成功的公开采集结果"),
        "xiaohongshu": SourceResult.unavailable(
            "xiaohongshu",
            "公开部署未启用小红书采集；本地路径必须明确选择后才会运行",
        ),
    }
    ordered_ids = ["guba", "xiaohongshu"]
    ordered_ids.extend(sorted(set(by_id) - set(ordered_ids)))
    return [_source_status(by_id.get(source_id, defaults.get(source_id))) for source_id in ordered_ids]


def _unavailable_market_context(*errors: str) -> dict[str, Any]:
    messages = [_public_error(error) for error in errors if error]
    if not messages:
        messages = ["未提供可用的市场快照。"]
    return {
        "status": "unavailable",
        "provider": None,
        "imported_at": None,
        "errors": messages,
        "sectors": {sector: None for sector in SECTOR_KEYS},
    }


def _public_market_sector(sector: str, value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    as_of = value.get("as_of")
    parsed_as_of = _parse_timestamp(as_of) if isinstance(as_of, str) else None
    raw_returns = value.get("returns")
    reference = MARKET_REFERENCES[sector]
    if (
        value.get("symbol") != reference["symbol"]
        or value.get("name") != reference["name"]
        or parsed_as_of is None
        or not isinstance(raw_returns, dict)
    ):
        return None
    returns = {
        window: float(raw_returns[window])
        for window in _MARKET_RETURN_WINDOWS
        if (
            window in raw_returns
            and isinstance(raw_returns[window], (int, float))
            and not isinstance(raw_returns[window], bool)
            and math.isfinite(float(raw_returns[window]))
        )
    }
    if not returns:
        return None
    return {
        "symbol": reference["symbol"],
        "name": reference["name"],
        "as_of": isoformat_utc(parsed_as_of),
        "returns": returns,
    }


def _public_market_context(value: Any) -> dict[str, Any]:
    """Normalize a validated snapshot or context into the public v3 contract."""

    if not isinstance(value, dict):
        return _unavailable_market_context()
    raw_sectors = value.get("sectors")
    provider = value.get("provider")
    imported_at = value.get("imported_at")
    parsed_imported_at = (
        _parse_timestamp(imported_at) if isinstance(imported_at, str) else None
    )
    if (
        not isinstance(raw_sectors, dict)
        or not isinstance(provider, str)
        or not provider.strip()
        or parsed_imported_at is None
    ):
        return _unavailable_market_context("市场快照缺少有效的来源或导入时间。")
    requested_status = value.get("status")
    if requested_status not in {None, "available", "degraded", "unavailable"}:
        return _unavailable_market_context("市场快照状态无效。")

    sectors = {
        sector: _public_market_sector(sector, raw_sectors.get(sector))
        for sector in SECTOR_KEYS
    }
    available_count = sum(item is not None for item in sectors.values())
    if requested_status == "unavailable" or available_count == 0:
        raw_errors = value.get("errors", [])
        errors = (
            [_public_error(str(error)) for error in raw_errors]
            if isinstance(raw_errors, list)
            else []
        )
        return _unavailable_market_context(*errors)

    status = "available" if available_count == len(SECTOR_KEYS) else "degraded"
    if requested_status == "degraded":
        status = "degraded"
    raw_errors = value.get("errors", [])
    errors = (
        [_public_error(str(error)) for error in raw_errors]
        if isinstance(raw_errors, list)
        else []
    )
    return {
        "status": status,
        "provider": _public_error(provider.strip())[:80],
        "imported_at": isoformat_utc(parsed_imported_at),
        "errors": list(dict.fromkeys(errors))[:20],
        "sectors": sectors,
    }


def build_payload(
    history: dict[str, Any],
    source_results: list[SourceResult],
    *,
    generated_at: datetime | None = None,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create schema-v3 output without raw records or author identities."""

    now = generated_at or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    records = history.get("records", [])
    latest_record = records[-1] if records else None
    last_success = _parse_timestamp(history.get("last_success_at"))
    stale = last_success is None or now - last_success > timedelta(hours=STALE_AFTER_HOURS)

    warnings: list[str] = []
    for source in source_results:
        for error in source.errors:
            warnings.append(f"{source.label}: {_public_error(error)}"[:300])
        if source.mode == "simulated":
            warnings.append(f"{source.label}: 当前为明确启用的模拟数据 (simulated)")
        elif source.mode == "imported":
            warnings.append(f"{source.label}: 当前为本地清洗后导入数据 (imported)")
    if last_success is None:
        warnings.append("尚无可用的最后一次成功实时读数。")
    elif stale:
        warnings.append(f"最后一次成功读数已超过 {STALE_AFTER_HOURS} 小时。")

    latest = None
    if isinstance(latest_record, dict):
        sectors = latest_record.get("sectors", {})
        if isinstance(sectors, dict) and all(sector in sectors for sector in SECTOR_KEYS):
            latest = {
                "date": str(latest_record.get("date", "")),
                "sectors": {
                    sector: _public_sector(sectors[sector])
                    for sector in SECTOR_KEYS
                },
            }

    sector_history: dict[str, list[dict[str, Any]]] = {sector: [] for sector in SECTOR_KEYS}
    for record in records:
        if not isinstance(record, dict):
            continue
        sectors = record.get("sectors", {})
        mode = record.get("source_mode", "live")
        if mode not in {"live", "imported", "simulated"}:
            continue
        for sector in SECTOR_KEYS:
            sector_value = sectors.get(sector) if isinstance(sectors, dict) else None
            if isinstance(sector_value, dict) and isinstance(sector_value.get("index"), (int, float)):
                sector_history[sector].append(
                    {
                        "date": str(record.get("date", "")),
                        "index": float(sector_value["index"]),
                        "source_mode": mode,
                    }
                )

    public_market_context = _public_market_context(market_context)
    if public_market_context["status"] != "available":
        warnings.append(
            "市场背景数据不可用或不完整；社交指数仍按独立公式展示，未使用行情数据。"
        )

    return {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "generated_at": isoformat_utc(now),
        "display_timezone": DISPLAY_TIMEZONE,
        "sources": _ordered_sources(source_results),
        "freshness": {
            "is_stale": stale,
            "last_success_at": isoformat_utc(last_success) if last_success else None,
            "stale_after_hours": STALE_AFTER_HOURS,
        },
        "warnings": list(dict.fromkeys(warnings)),
        "methodology": copy.deepcopy(METHODOLOGY),
        "latest": latest,
        "sector_history": sector_history,
        "market_context": public_market_context,
        "record_count": len(records),
    }
