"""Deprecated compatibility shim for the package CLI.

New automation should use ``python -m mom_index all``.
"""

from __future__ import annotations

import json
import sys

from mom_index.cli import main
from mom_index.config import DEFAULT_DATA_DIR


def run_pipeline() -> dict:
    """Run the canonical pipeline and return the generated public payload."""

    exit_code = main(["all"])
    if exit_code:
        raise RuntimeError(f"mom_index pipeline exited with status {exit_code}")
    with (DEFAULT_DATA_DIR / "dashboard_data.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    raise SystemExit(main(["all", *sys.argv[1:]]))
