"""Build the privacy-preserving public dashboard payload."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from mom_index.collectors import SourceResult
from mom_index.config import (
    DISPLAY_TIMEZONE,
    METHODOLOGY,
    SECTOR_KEYS,
    STALE_AFTER_HOURS,
    isoformat_utc,
    utc_now,
)

_ALLOWED_POST_HOSTS = {
    "guba.eastmoney.com",
    "caifuhao.eastmoney.com",
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
_PROXY_CREDENTIAL = re.compile(r"(https?://)[^/@\s]+@", re.IGNORECASE)


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
    return message[:240]


def _public_url(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_POST_HOSTS:
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


def build_payload(
    history: dict[str, Any],
    source_results: list[SourceResult],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Create schema-v2 output without raw records or author identities."""

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
        if mode not in {"live", "simulated"}:
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

    return {
        "schema_version": 2,
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
        "record_count": len(records),
    }
