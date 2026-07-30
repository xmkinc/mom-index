"""Local-only, API-key-gated Xiaohongshu collector.

This module is deliberately absent from the unattended public collector registry.
"""

from __future__ import annotations

import os
import re
from typing import Any

from mom_index.config import SECTOR_KEYS, SOURCE_LABELS, isoformat_utc, optional_proxy

from . import SourceResult

API_BASE = "https://rnote.dev/api/v2"
SEARCH_KEYWORDS = {
    "nasdaq": ["美股怎么买", "纳斯达克新手", "纳指还能买吗"],
    "gold": ["黄金怎么买", "买黄金亏了", "黄金还能涨吗"],
    "cpo": ["CPO是什么", "光模块还能涨吗", "通信ETF"],
    "semiconductor": ["芯片还能买吗", "半导体新手", "芯片ETF"],
}
_PROXY_CREDENTIAL_PATTERN = re.compile(r"(https?://)[^/@\s]+@", re.IGNORECASE)


def _safe_error(error: Exception | str) -> str:
    message = " ".join(str(error).split())
    return _PROXY_CREDENTIAL_PATTERN.sub(r"\1***@", message)[:180]


class XhsRnoteCollector:
    """Collect XHS notes only when a user explicitly provides an API key."""

    source_id = "xiaohongshu"
    label = SOURCE_LABELS["xiaohongshu"]

    def __init__(self, api_key: str | None = None, *, timeout: float = 15.0) -> None:
        self.api_key = (api_key or os.environ.get("RNODE_API_KEY", "")).strip()
        self.timeout = timeout

    def _search(self, keyword: str, count: int = 5) -> list[dict[str, Any]]:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("requests is required for local rnote collection") from exc

        kwargs: dict[str, Any] = {}
        proxy = optional_proxy()
        if proxy:
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        response = requests.get(
            f"{API_BASE}/crawler/search/notes",
            params={"keyword": keyword, "count": count, "sort": "general"},
            headers={"X-API-Key": self.api_key, "User-Agent": "mom-index/2.0"},
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("data", {}).get("data", {}).get("items", [])
        return [self._parse_note(item.get("note") or item.get("note_card") or item) for item in items]

    @staticmethod
    def _parse_note(raw: dict[str, Any]) -> dict[str, Any]:
        note_id = str(raw.get("id") or raw.get("note_id") or "")
        return {
            "id": f"xhs_{note_id}" if note_id else "",
            "title": str(raw.get("title") or raw.get("desc") or "")[:200],
            "content": str(raw.get("desc") or raw.get("content") or ""),
            "url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
            "platform": "xiaohongshu",
            "collected_at": isoformat_utc(),
        }

    def collect(self) -> SourceResult:
        if not self.api_key:
            return SourceResult.unavailable(
                self.source_id,
                "local-only rnote collection disabled: RNODE_API_KEY is not configured",
            )

        posts: dict[str, list[dict[str, Any]]] = {sector: [] for sector in SECTOR_KEYS}
        errors: list[str] = []
        collected_at = isoformat_utc()
        for sector, keywords in SEARCH_KEYWORDS.items():
            seen: set[str] = set()
            try:
                for keyword in keywords:
                    for note in self._search(keyword):
                        identity = note.get("id") or note.get("url") or note.get("title")
                        if identity and identity not in seen:
                            seen.add(str(identity))
                            note["collected_at"] = collected_at
                            posts[sector].append(note)
                if not posts[sector]:
                    errors.append(f"{sector}: zero valid notes")
            except Exception as exc:
                errors.append(f"{sector}: {_safe_error(exc)}")

        if errors:
            return SourceResult(
                source_id=self.source_id,
                label=self.label,
                mode="unavailable",
                posts=posts,
                errors=errors,
            )
        return SourceResult(
            source_id=self.source_id,
            label=self.label,
            mode="live",
            posts=posts,
            collected_at=collected_at,
        )


def collect_all() -> dict[str, list[dict[str, Any]]]:
    """Compatibility helper for explicit local runs."""

    result = XhsRnoteCollector().collect()
    return result.posts if result.mode == "live" else {sector: [] for sector in SECTOR_KEYS}
