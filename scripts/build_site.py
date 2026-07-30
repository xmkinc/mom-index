#!/usr/bin/env python3
"""Assemble a clean static-site artifact for the 宝妈指数 dashboard.

Copies ``frontend/*`` (excluding the gitignored ``frontend/data/`` build-output
directory) and the schema-v3 public payload ``data/dashboard_data.json`` into
a deterministic ``_site/`` tree with only relative, subpath-safe references.

Usage:
    python scripts/build_site.py --out _site
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
PAYLOAD_SRC = REPO_ROOT / "data" / "dashboard_data.json"

# Paths inside frontend/ that are build output / not part of the shipped site.
EXCLUDED_FRONTEND_RELS = {
    Path("data"),  # gitignored build output; replaced by the canonical payload
}


def _copy_tree(src: Path, dst: Path, skip: set[Path] | None = None) -> list[Path]:
    """Copy ``src`` into ``dst`` deterministically, returning copied files."""
    skip = skip or set()
    copied: list[Path] = []
    if not src.is_dir():
        raise NotADirectoryError(src)
    dst.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src.iterdir()):
        rel = entry.relative_to(src)
        if rel in skip:
            continue
        target = dst / rel
        if entry.is_dir():
            sub = _copy_tree(entry, target)
            copied.extend(sub)
        else:
            shutil.copy2(entry, target)
            copied.append(target)
    return copied


def build(out_dir: Path) -> list[Path]:
    if not FRONTEND_DIR.is_dir():
        raise FileNotFoundError(f"frontend directory not found: {FRONTEND_DIR}")
    if not PAYLOAD_SRC.is_file():
        raise FileNotFoundError(f"public payload not found: {PAYLOAD_SRC}")
    try:
        payload = json.loads(PAYLOAD_SRC.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f"public payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 3:
        raise ValueError("public payload must be a schema-v3 object")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # 1. Frontend assets (HTML, CSS, JS, vendored Chart.js, LICENSE notice).
    copied = _copy_tree(FRONTEND_DIR, out_dir, skip=EXCLUDED_FRONTEND_RELS)

    # 2. Single public payload, under a relative data/ subpath.
    payload_dst = out_dir / "data" / "dashboard_data.json"
    payload_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PAYLOAD_SRC, payload_dst)
    copied.append(payload_dst)

    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="_site",
        help="output directory (default: _site)",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out).resolve()
    # Resolve relative to repo root so the command works from any CWD.
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()

    try:
        copied = build(out_dir)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(f"build_site: ERROR: {exc}", file=sys.stderr)
        return 2

    # Deterministic listing for reproducible logs.
    rel_copied = sorted(p.relative_to(out_dir).as_posix() for p in copied)
    print(f"build_site: wrote {len(rel_copied)} files to {out_dir}")
    for rel in rel_copied:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
