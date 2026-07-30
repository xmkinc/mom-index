"""Polite request headers and delays for unauthenticated public collection."""

from __future__ import annotations

import os
import random
import time

USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
)


def request_headers(*, referer: str | None = None) -> dict[str, str]:
    """Return ordinary browser-like headers without fingerprint spoofing."""

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def polite_delay(min_seconds: float = 0.8, max_seconds: float = 1.8) -> None:
    """Apply a small inter-board delay unless tests explicitly disable it."""

    if os.environ.get("MOM_INDEX_SKIP_DELAYS", "").lower() in {"1", "true", "yes"}:
        return
    time.sleep(random.uniform(min_seconds, max_seconds))
