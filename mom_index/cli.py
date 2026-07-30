"""Command-line interface used by local runs and unattended workflows."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from mom_index.analysis import analyze_all, compute_sector_index
from mom_index.collectors import SourceResult, get_public_collectors
from mom_index.collectors.simulated import collect_simulated
from mom_index.config import DEFAULT_DATA_DIR, SECTOR_KEYS
from mom_index.export import build_payload
from mom_index.storage import (
    load_collection,
    load_history,
    merge_success,
    save_collection,
    save_history,
    write_json,
)
from mom_index.validation import PayloadValidationError, validate_payload, validate_payload_file


def _path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def collect_sources(
    *,
    source_names: list[str],
    allow_simulated: bool,
    data_dir: Path,
) -> list[SourceResult]:
    registry = get_public_collectors()
    results: list[SourceResult] = []
    for name in dict.fromkeys(source_names):
        if name == "xhs-rnote":
            from mom_index.collectors.xhs_rnote import XhsRnoteCollector

            results.append(XhsRnoteCollector().collect())
            continue
        collector_type = registry.get(name)
        if collector_type is None:
            raise ValueError(f"Unsupported public source: {name}")
        results.append(collector_type().collect())

    xhs_result = next((item for item in results if item.source_id == "xiaohongshu"), None)
    if allow_simulated and (xhs_result is None or xhs_result.mode != "live"):
        results = [item for item in results if item.source_id != "xiaohongshu"]
        results.append(collect_simulated())
    elif xhs_result is None:
        results.append(
            SourceResult.unavailable(
                "xiaohongshu",
                "public Xiaohongshu collection is disabled; use an explicit local-only path",
            )
        )
    save_collection(data_dir, results)
    return results


def build_dashboard(data_dir: Path, output_path: Path) -> tuple[dict, str]:
    history = load_history(data_dir)
    source_results = load_collection(data_dir)
    eligible = [
        result
        for result in source_results
        if result.mode in {"live", "simulated"} and result.post_count > 0
    ]
    sector_posts = {sector: [] for sector in SECTOR_KEYS}
    for result in eligible:
        for sector in SECTOR_KEYS:
            sector_posts[sector].extend(result.posts.get(sector, []))

    if eligible and all(sector_posts[sector] for sector in SECTOR_KEYS):
        analyses = analyze_all(sector_posts)
        sector_indices = {
            sector: compute_sector_index(analyses[sector])
            for sector in SECTOR_KEYS
        }
        timestamps = [result.collected_at for result in eligible if result.collected_at]
        if not timestamps:
            raise ValueError("Successful collection results must include collected_at")
        source_mode = "simulated" if any(result.mode == "simulated" for result in eligible) else "live"
        history = merge_success(
            history,
            sector_indices,
            collected_at=max(timestamps),
            source_mode=source_mode,
        )
        save_history(data_dir, history)
    elif not (data_dir / "history.json").exists():
        save_history(data_dir, history)

    payload = build_payload(history, source_results)
    engine = validate_payload(payload)
    write_json(output_path, payload)
    return payload, engine


def _cmd_collect(args: argparse.Namespace) -> int:
    data_dir = _path(args.out)
    results = collect_sources(
        source_names=args.sources,
        allow_simulated=args.allow_simulated,
        data_dir=data_dir,
    )
    for result in results:
        errors = f", errors={len(result.errors)}" if result.errors else ""
        print(f"{result.source_id}: mode={result.mode}, posts={result.post_count}{errors}")
    print(f"collection state: {data_dir / 'collection.json'}")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    data_dir = _path(args.data)
    output = _path(args.out) if args.out else data_dir / "dashboard_data.json"
    payload, engine = build_dashboard(data_dir, output)
    print(
        f"dashboard payload: {output} "
        f"(records={payload['record_count']}, stale={payload['freshness']['is_stale']}, validator={engine})"
    )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    payload = _path(args.payload)
    engine = validate_payload_file(payload)
    print(f"valid schema-v2 payload: {payload} ({engine})")
    return 0


def _cmd_all(args: argparse.Namespace) -> int:
    data_dir = _path(args.data)
    collect_sources(
        source_names=args.sources,
        allow_simulated=args.allow_simulated,
        data_dir=data_dir,
    )
    output = _path(args.out) if args.out else data_dir / "dashboard_data.json"
    payload, engine = build_dashboard(data_dir, output)
    print(
        f"pipeline complete: {output} "
        f"(records={payload['record_count']}, stale={payload['freshness']['is_stale']}, validator={engine})"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mom_index",
        description="Collect, build, and validate the truthful Mom Index public payload.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="collect source data with explicit source states")
    collect.add_argument(
        "--sources",
        nargs="+",
        default=["guba"],
        choices=["guba", "xhs-rnote"],
        help="sources to collect; XHS rnote is explicit local-only",
    )
    collect.add_argument(
        "--allow-simulated",
        action="store_true",
        help="explicitly add labeled local demo posts; never enabled by default",
    )
    collect.add_argument("--out", default=str(DEFAULT_DATA_DIR), help="data-state directory")
    collect.set_defaults(handler=_cmd_collect)

    build = subparsers.add_parser("build", help="update LKG on success and build schema-v2 output")
    build.add_argument("--data", default=str(DEFAULT_DATA_DIR), help="data-state directory")
    build.add_argument("--out", help="dashboard JSON path (default: <data>/dashboard_data.json)")
    build.set_defaults(handler=_cmd_build)

    validate = subparsers.add_parser("validate", help="validate a public dashboard payload")
    validate.add_argument("payload", help="path to dashboard JSON")
    validate.set_defaults(handler=_cmd_validate)

    all_command = subparsers.add_parser("all", help="collect, build, and validate in one command")
    all_command.add_argument(
        "--sources",
        nargs="+",
        default=["guba"],
        choices=["guba", "xhs-rnote"],
    )
    all_command.add_argument("--allow-simulated", action="store_true")
    all_command.add_argument("--data", default=str(DEFAULT_DATA_DIR), help="data-state directory")
    all_command.add_argument("--out", help="dashboard JSON path")
    all_command.set_defaults(handler=_cmd_all)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError, PayloadValidationError) as exc:
        parser.error(str(exc))
    return 2
