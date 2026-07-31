"""Objective, deterministic sample-quality computation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from mom_index.config import CONFIDENCE_MODEL_VERSION


def _parse_post_time(post: dict[str, Any]) -> datetime | None:
    """Return a timezone-aware UTC timestamp or None if unknown/unparseable."""
    for key in ("published_at", "published_time", "time", "created_at", "timestamp"):
        value = post.get(key)
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if parsed.tzinfo is None:
            continue
        return parsed.astimezone(timezone.utc)
    return None


def compute_sample_quality(
    posts: List[dict[str, Any]],
    results: List[Any],
    now: datetime,
    window_hours: int = 72,
) -> dict[str, Any]:
    """Compute deterministic sample-quality metrics for a sector.

    Low confidence applies when valid sample size <30, title-only ratio >0.8,
    or classifier-evidence coverage <0.3.  High confidence requires sample
    size >=60, title-only ratio <=0.4, evidence coverage >=0.5, and known
    in-window ratio >=0.6.  Otherwise medium.
    """
    result_by_id = {r.post_id: r for r in results}

    valid_sample_size = 0
    title_only_count = 0
    evidence_count = 0
    in_window_count = 0
    unknown_time_count = 0
    platform_counts: dict[str, int] = {}

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    for post in posts:
        post_id = str(post.get("id", ""))
        result = result_by_id.get(post_id)
        if result is None or getattr(result, "level", "") == "垃圾帖":
            continue

        valid_sample_size += 1
        platform = post.get("platform", getattr(result, "platform", "unknown"))
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

        if not getattr(result, "has_content", False):
            title_only_count += 1

        has_evidence = bool(
            getattr(result, "matched_newbie", [])
            or getattr(result, "matched_pro", [])
            or getattr(result, "matched_extension_signals", [])
        )
        if has_evidence:
            evidence_count += 1

        post_time = _parse_post_time(post)
        if post_time is None:
            unknown_time_count += 1
        elif post_time >= window_start:
            in_window_count += 1

    title_only_ratio = (
        title_only_count / valid_sample_size if valid_sample_size else 0.0
    )
    evidence_coverage = (
        evidence_count / valid_sample_size if valid_sample_size else 0.0
    )
    known_in_window_ratio = (
        in_window_count / valid_sample_size if valid_sample_size else 0.0
    )
    unknown_time_ratio = (
        unknown_time_count / valid_sample_size if valid_sample_size else 0.0
    )

    reason_codes = []
    if valid_sample_size == 0:
        reason_codes.append("empty_sample")
    if valid_sample_size < 30:
        reason_codes.append("sample_size_below_30")
    if valid_sample_size < 60:
        reason_codes.append("sample_size_below_60")
    if title_only_ratio > 0.8:
        reason_codes.append("title_only_ratio_above_0_8")
    elif title_only_ratio > 0.4:
        reason_codes.append("title_only_ratio_above_0_4")
    if evidence_coverage < 0.3:
        reason_codes.append("classifier_evidence_coverage_below_0_3")
    elif evidence_coverage < 0.5:
        reason_codes.append("classifier_evidence_coverage_below_0_5")
    if known_in_window_ratio < 0.6:
        reason_codes.append("known_in_window_ratio_below_0_6")

    if (
        valid_sample_size == 0
        or valid_sample_size < 30
        or title_only_ratio > 0.8
        or evidence_coverage < 0.3
    ):
        confidence = "low"
    elif (
        valid_sample_size >= 60
        and title_only_ratio <= 0.4
        and evidence_coverage >= 0.5
        and known_in_window_ratio >= 0.6
    ):
        confidence = "high"
    else:
        confidence = "medium"

    return {
        "model_version": CONFIDENCE_MODEL_VERSION,
        "confidence": confidence,
        "valid_sample_size": valid_sample_size,
        "title_only_ratio": round(title_only_ratio, 4),
        "platform_counts": platform_counts,
        "classifier_evidence_coverage": round(evidence_coverage, 4),
        "known_in_window_ratio": round(known_in_window_ratio, 4),
        "unknown_time_ratio": round(unknown_time_ratio, 4),
        "window_hours": window_hours,
        "reason_codes": reason_codes,
    }
