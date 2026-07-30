"""Unauthenticated Eastmoney Guba collector with row-scoped parsing."""

from __future__ import annotations

import hashlib
import os
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from mom_index.config import SECTORS, SOURCE_LABELS, isoformat_utc, optional_proxy

from . import SourceResult
from .anti_detection import polite_delay, request_headers

GUBA_ORIGIN = "https://guba.eastmoney.com"
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_SECRET_PATTERN = re.compile(r"(?i)(token|secret|cookie|authorization|api[_-]?key)\s*[:=]\s*\S+")
_PROXY_CREDENTIAL_PATTERN = re.compile(r"(https?://)[^/@\s]+@", re.IGNORECASE)


def _class_tokens(attrs: list[tuple[str, str | None]]) -> set[str]:
    classes = next((value or "" for key, value in attrs if key == "class"), "")
    return set(classes.split())


class _GubaRowParser(HTMLParser):
    """Extract fields only from within one post row at a time."""

    def __init__(self, collected_at: str) -> None:
        super().__init__(convert_charrefs=True)
        self.collected_at = collected_at
        self.posts: list[dict[str, Any]] = []
        self._row: dict[str, Any] | None = None
        self._depth = 0
        self._capture: str | None = None
        self._capture_tag: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tokens = _class_tokens(attrs)
        starts_row = (
            (tag == "div" and bool(tokens & {"articleh", "listitem"}))
            or tag == "tr"
        )
        if self._row is None:
            if not starts_row:
                return
            self._row = {"title": "", "href": "", "reads": "", "replies": "", "date": ""}
            self._depth = 1
        elif tag not in _VOID_TAGS:
            self._depth += 1

        if self._row is None:
            return

        attrs_dict = dict(attrs)
        if tag == "a":
            href = (attrs_dict.get("href") or "").strip()
            if "/news," in href or href.startswith("news,"):
                self._row["href"] = href
                title = (attrs_dict.get("title") or "").strip()
                if title:
                    self._row["title"] = title
                self._capture = "anchor"
                self._capture_tag = "a"
                self._anchor_text = []

        field = None
        if "l1" in tokens:
            field = "reads"
        elif "l2" in tokens:
            field = "replies"
        elif "l5" in tokens:
            field = "date"
        if field:
            self._capture = field
            self._capture_tag = tag

    def handle_data(self, data: str) -> None:
        if self._row is None or not self._capture:
            return
        if self._capture == "anchor":
            self._anchor_text.append(data)
        else:
            self._row[self._capture] += data

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        if self._capture_tag == tag:
            if self._capture == "anchor" and not self._row["title"]:
                self._row["title"] = " ".join(self._anchor_text)
            self._capture = None
            self._capture_tag = None
            self._anchor_text = []

        if tag not in _VOID_TAGS:
            self._depth -= 1
        if self._depth == 0:
            self._finish_row()

    def close(self) -> None:
        super().close()
        if self._row is not None:
            self._finish_row()

    def _finish_row(self) -> None:
        assert self._row is not None
        title = " ".join(str(self._row["title"]).split()).strip()
        href = str(self._row["href"]).strip()
        if title and title != "点击开始搜索" and href:
            source_url = _normalize_source_url(href)
            if source_url:
                digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:20]
                self.posts.append(
                    {
                        "id": f"guba_{digest}",
                        "title": title[:200],
                        "content": "",
                        "url": source_url,
                        "platform": "guba",
                        "reads": " ".join(str(self._row["reads"]).split()) or "0",
                        "replies": " ".join(str(self._row["replies"]).split()) or "0",
                        "date": " ".join(str(self._row["date"]).split()) or "未知",
                        "collected_at": self.collected_at,
                    }
                )
        self._row = None
        self._depth = 0
        self._capture = None
        self._capture_tag = None
        self._anchor_text = []


def _normalize_source_url(href: str) -> str:
    if href.startswith("news,"):
        href = f"/{href}"
    value = urljoin(f"{GUBA_ORIGIN}/", href)
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"guba.eastmoney.com", "caifuhao.eastmoney.com"}:
        return ""
    return value


def parse_posts(html_content: str, *, collected_at: str | None = None) -> list[dict[str, Any]]:
    """Parse post rows without positionally zipping unrelated page-wide fields."""

    parser = _GubaRowParser(collected_at or isoformat_utc())
    parser.feed(html_content)
    parser.close()
    return parser.posts


def _safe_error(error: Exception | str) -> str:
    message = " ".join(str(error).split())
    message = _PROXY_CREDENTIAL_PATTERN.sub(r"\1***@", message)
    message = _SECRET_PATTERN.sub(r"\1=***", message)
    return message[:240] or "unknown collection error"


class GubaCollector:
    """Collect one list page for each configured sector."""

    source_id = "guba"
    label = SOURCE_LABELS["guba"]

    def __init__(self, *, timeout: float = 15.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries

    def _session(self):
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
        except ImportError as exc:
            raise RuntimeError("requests is required for live Guba collection") from exc

        session = requests.Session()
        session.trust_env = False
        retry = Retry(
            total=self.retries,
            connect=self.retries,
            read=self.retries,
            status=self.retries,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        proxy = optional_proxy()
        if proxy:
            session.proxies.update({"http": proxy, "https": proxy})
        return session

    def fetch_board(self, session, code: str) -> str:
        url = f"{GUBA_ORIGIN}/list,{code}.html"
        response = session.get(
            url,
            headers=request_headers(referer=GUBA_ORIGIN),
            timeout=self.timeout,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def collect(self) -> SourceResult:
        if os.environ.get("MOM_INDEX_FORCE_COLLECTION_FAILURE", "").lower() in {"1", "true", "yes"}:
            return SourceResult.unavailable(self.source_id, "forced collection failure")

        collected_at = isoformat_utc()
        posts: dict[str, list[dict[str, Any]]] = {}
        errors: list[str] = []
        try:
            session = self._session()
        except Exception as exc:
            return SourceResult.unavailable(self.source_id, _safe_error(exc))

        for position, (sector, config) in enumerate(SECTORS.items()):
            try:
                parsed = parse_posts(self.fetch_board(session, config["code"]), collected_at=collected_at)
                posts[sector] = parsed
                if not parsed:
                    errors.append(f"{sector}: zero valid post rows")
            except Exception as exc:
                posts[sector] = []
                errors.append(f"{sector}: {_safe_error(exc)}")
            if position < len(SECTORS) - 1:
                polite_delay()

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
    """Compatibility helper returning posts only when collection fully succeeds."""

    result = GubaCollector().collect()
    return result.posts if result.mode == "live" else {sector: [] for sector in SECTORS}


if __name__ == "__main__":
    outcome = GubaCollector().collect()
    print(outcome.to_dict())
