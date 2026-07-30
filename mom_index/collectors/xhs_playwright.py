"""Explicit local-only Xiaohongshu Playwright entry point.

Interactive-login browser collection is never imported by or registered with the
public pipeline. Users must opt in locally and manage their own compliant session.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import SourceResult


def collect_local_profile() -> SourceResult:
    """Return an explicit unavailable state unless a local profile is configured.

    A compliant browser implementation can be added behind this boundary without
    changing the public collection path or silently falling back to sample data.
    """

    profile = os.environ.get("MOM_INDEX_XHS_PROFILE", "").strip()
    if not profile:
        return SourceResult.unavailable(
            "xiaohongshu",
            "local Playwright collection disabled: MOM_INDEX_XHS_PROFILE is not configured",
        )
    if not Path(profile).expanduser().is_dir():
        return SourceResult.unavailable(
            "xiaohongshu",
            "local Playwright collection disabled: configured profile does not exist",
        )
    try:
        import playwright  # noqa: F401
    except ImportError:
        return SourceResult.unavailable(
            "xiaohongshu",
            "local Playwright collection disabled: optional playwright dependency is not installed",
        )
    return SourceResult.unavailable(
        "xiaohongshu",
        "local Playwright adapter requires an explicit compliant implementation; public automation remains disabled",
    )
