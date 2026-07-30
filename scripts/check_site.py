#!/usr/bin/env python3
"""Smoke-check the assembled static-site artifact.

Verifies, against the accepted design contract:
  * ``index.html`` and the single public payload ``data/dashboard_data.json``
    exist and the payload validates against ``schema/dashboard.schema.json``;
  * every relative asset reference in ``index.html`` resolves inside the site;
  * no CDN / absolute-URL runtime dependencies (``https://``/``http://`` in
    ``src``/``href``), no absolute ``/mom-index/`` paths; ``data:`` URIs allowed;
  * no secret-like strings (tokens, cookies, credentials, the old hardcoded
    proxy) anywhere in the built artifact;
  * no fabricated source claims — "抖音"/"Douyin" must not appear, and a
    source whose mode is ``unavailable`` must not be described as live;
  * the vendored Chart.js runtime is present and referenced.

Usage:
    python scripts/check_site.py _site
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "dashboard.schema.json"

# Patterns that should never appear in a published artifact.
SECRET_PATTERNS = [
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret[_-]?key", re.IGNORECASE),
    re.compile(r"\baccess[_-]?token\b", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"\bauthorization\s*:", re.IGNORECASE),
    re.compile(r"\bpassword\s*[:=]\s*\S", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),  # OpenAI-style key
    re.compile(r"\bgh[ps]_[A-Za-z0-9]{36,}\b"),  # GitHub token
    re.compile(r"\bcookie\s*:", re.IGNORECASE),
    re.compile(r"\bset-cookie\b", re.IGNORECASE),
    re.compile(r"127\.0\.0\.1:7890"),  # old hardcoded proxy
]

FORBIDDEN_TERMS = ["抖音", "Douyin"]


class LinkExtractor(HTMLParser):
    """Collects src/href attributes for asset-reference validation."""

    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in ("src", "href") and value:
                self.refs.append(value)


class Failure(Exception):
    pass


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_payload(site: Path) -> dict:
    payload_path = site / "data" / "dashboard_data.json"
    if not payload_path.is_file():
        raise Failure(f"missing public payload: {payload_path.relative_to(site)}")
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Failure(f"payload is not valid JSON: {exc}") from exc

    if not SCHEMA_PATH.is_file():
        raise Failure(f"schema not found: {SCHEMA_PATH}")
    try:
        import jsonschema  # type: ignore
    except ImportError as exc:
        raise Failure(f"jsonschema package not available: {exc}") from exc

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = []
        for err in errors:
            loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
            msgs.append(f"  {loc}: {err.message}")
        raise Failure("payload failed schema validation:\n" + "\n".join(msgs))

    # Truthful-source consistency: an unavailable source must not be described
    # as live; xiaohongshu must not be reported as live in the public payload.
    for src in payload.get("sources", []):
        if src.get("mode") == "unavailable" and src.get("collected_at") is not None:
            raise Failure(
                f"source {src.get('id')!r} is unavailable but carries a collected_at"
            )
        if src.get("id") == "xiaohongshu" and src.get("mode") == "live":
            raise Failure("xiaohongshu must not be reported as live in the public payload")
    return payload


def _check_index(site: Path) -> str:
    index_path = site / "index.html"
    if not index_path.is_file():
        raise Failure("missing index.html")
    html = _read_text(index_path)

    if "抖音" in html or "Douyin" in html or "douyin" in html:
        raise Failure("index.html contains a fabricated Douyin/抖音 source claim")

    parser = LinkExtractor()
    parser.feed(html)
    for ref in parser.refs:
        if ref.startswith("data:"):
            continue  # inline favicon, allowed
        if ref.startswith(("http://", "https://")):
            raise Failure(f"CDN/absolute runtime URL in index.html: {ref}")
        if ref.startswith("//"):
            raise Failure(f"protocol-relative runtime URL in index.html: {ref}")
        if ref.startswith("/"):
            raise Failure(f"absolute path (non-subpath-safe) in index.html: {ref}")
        target = (site / ref).resolve()
        try:
            target.relative_to(site.resolve())
        except ValueError:
            raise Failure(f"asset reference escapes site root: {ref}") from None
        if not target.is_file():
            raise Failure(f"broken asset reference in index.html: {ref} -> {target}")

    # Vendored Chart.js must be present and referenced.
    chartjs = site / "assets" / "chart.umd.min.js"
    if not chartjs.is_file():
        raise Failure("vendored Chart.js runtime missing at assets/chart.umd.min.js")
    if "assets/chart.umd.min.js" not in html:
        raise Failure("index.html does not reference the vendored Chart.js runtime")
    return html


def _iter_site_files(site: Path):
    for p in sorted(site.rglob("*")):
        if p.is_file():
            yield p


def _check_secrets_and_terms(site: Path, payload: dict) -> None:
    # Scan all text files in the artifact for secret-like strings + forbidden terms.
    scanned: list[Path] = []
    for path in _iter_site_files(site):
        # Skip the (potentially large) vendored minified JS for secret-keyword
        # scanning — it is third-party MIT code we do not author. It is still
        # checked for forbidden source-claim terms below via a separate pass.
        if path.name == "chart.umd.min.js":
            continue
        try:
            text = _read_text(path)
        except UnicodeDecodeError:
            continue
        scanned.append(path)
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                raise Failure(
                    f"secret-like string {m.group(0)!r} found in "
                    f"{path.relative_to(site)}"
                )
        for term in FORBIDDEN_TERMS:
            if term in text:
                raise Failure(
                    f"forbidden term {term!r} found in {path.relative_to(site)}"
                )

    # Also scan the vendored Chart.js only for forbidden source-claim terms
    # (not secret keywords — those would be false positives in minified JS).
    chartjs = site / "assets" / "chart.umd.min.js"
    if chartjs.is_file():
        text = _read_text(chartjs)
        for term in FORBIDDEN_TERMS:
            if term in text:
                raise Failure(
                    f"forbidden term {term!r} found in {chartjs.relative_to(site)}"
                )

    # Payload-level forbidden terms (defense in depth).
    payload_text = json.dumps(payload, ensure_ascii=False)
    for term in FORBIDDEN_TERMS:
        if term in payload_text:
            raise Failure(f"forbidden term {term!r} found in dashboard payload")


def check(site: Path) -> None:
    if not site.is_dir():
        raise Failure(f"site directory does not exist: {site}")
    payload = _check_payload(site)
    _check_index(site)
    _check_secrets_and_terms(site, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", help="path to the assembled _site directory")
    args = parser.parse_args(argv)

    site = Path(args.site).resolve()
    try:
        check(site)
    except Failure as exc:
        print(f"check_site: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"check_site: OK ({site})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
