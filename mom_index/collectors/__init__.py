"""Collection contracts and public collector registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mom_index.config import SOURCE_LABELS, isoformat_utc

VALID_SOURCE_MODES = {"live", "imported", "simulated", "unavailable"}


@dataclass
class SourceResult:
    """One collector's posts plus an explicit, truthful source state."""

    source_id: str
    label: str
    mode: str
    posts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    collected_at: str | None = None
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.mode not in VALID_SOURCE_MODES:
            raise ValueError(f"Unsupported source mode: {self.mode}")
        if self.mode == "unavailable":
            self.collected_at = None
        elif self.collected_at is None:
            self.collected_at = isoformat_utc()

    @property
    def post_count(self) -> int:
        return sum(len(items) for items in self.posts.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.source_id,
            "label": self.label,
            "mode": self.mode,
            "collected_at": self.collected_at,
            "post_count": self.post_count,
            "errors": list(self.errors),
            "posts": self.posts,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceResult":
        raw_posts = value.get("posts", {})
        posts = {
            str(sector): [item for item in items if isinstance(item, dict)]
            for sector, items in raw_posts.items()
            if isinstance(items, list)
        } if isinstance(raw_posts, dict) else {}
        raw_errors = value.get("errors", [])
        return cls(
            source_id=str(value.get("id", "unknown")),
            label=str(value.get("label", value.get("id", "unknown"))),
            mode=str(value.get("mode", "unavailable")),
            posts=posts,
            collected_at=value.get("collected_at"),
            errors=[str(item) for item in raw_errors] if isinstance(raw_errors, list) else [],
        )

    @classmethod
    def unavailable(
        cls,
        source_id: str,
        error: str,
        *,
        posts: dict[str, list[dict[str, Any]]] | None = None,
    ) -> "SourceResult":
        return cls(
            source_id=source_id,
            label=SOURCE_LABELS.get(source_id, source_id),
            mode="unavailable",
            posts=posts or {},
            errors=[error],
        )


def get_public_collectors() -> dict[str, type]:
    """Return collectors allowed in the unattended public path."""

    from .guba import GubaCollector

    return {"guba": GubaCollector}


__all__ = ["SourceResult", "VALID_SOURCE_MODES", "get_public_collectors"]
