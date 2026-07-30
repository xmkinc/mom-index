"""Command-line interface used by local runs and unattended workflows."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from mom_index.analysis import (
    analyze_all,
    compute_sample_quality,
    compute_sector_index,
)
from mom_index.collectors import SourceResult, get_public_collectors
from mom_index.collectors.simulated import collect_simulated
from mom_index.collectors.xhs_import import import_xhs_file
from mom_index.config import DEFAULT_DATA_DIR, SECTOR_KEYS
from mom_index.export import build_payload
from mom_index.market import import_snapshot
from mom_index.storage import (
    dominant_source_mode,
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
    xhs_import_path: Path | None = None,
) -> list[SourceResult]:
    registry = get_public_collectors()
    results: list[SourceResult] = []
    names = list(dict.fromkeys(source_names))
    if xhs_import_path is not None and "xhs-rnote" in names:
        raise ValueError(
            "--xhs-import cannot be combined with the legacy local xhs-rnote source"
        )

    for name in names:
        if name == "xhs-rnote":
            from mom_index.collectors.xhs_rnote import XhsRnoteCollector

            results.append(XhsRnoteCollector().collect())
            continue
        collector_type = registry.get(name)
        if collector_type is None:
            raise ValueError(f"Unsupported public source: {name}")
        results.append(collector_type().collect())

    if xhs_import_path is not None:
        results.append(import_xhs_file(xhs_import_path))

    xhs_result = next(
        (item for item in results if item.source_id == "xiaohongshu"),
        None,
    )
    if allow_simulated and (
        xhs_result is None or xhs_result.mode not in {"live", "imported"}
    ):
        results = [item for item in results if item.source_id != "xiaohongshu"]
        results.append(collect_simulated())
    elif xhs_result is None:
        results.append(
            SourceResult.unavailable(
                "xiaohongshu",
                "公开部署未启用小红书采集；如需使用，请在本地明确选择合规的数据路径",
            )
        )
    save_collection(data_dir, results)
    return results


def _parse_collected_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid source collected_at timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("Source collected_at timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def build_dashboard(
    data_dir: Path,
    output_path: Path,
    *,
    market_import_path: Path | None = None,
) -> tuple[dict, str]:
    history = load_history(data_dir)
    source_results = load_collection(data_dir)
    eligible = [
        result
        for result in source_results
        if result.mode in {"live", "imported", "simulated"} and result.post_count > 0
    ]
    sector_posts = {sector: [] for sector in SECTOR_KEYS}
    for result in eligible:
        for sector in SECTOR_KEYS:
            sector_posts[sector].extend(result.posts.get(sector, []))

    if eligible and all(sector_posts[sector] for sector in SECTOR_KEYS):
        analyses = analyze_all(sector_posts)
        timestamps = [
            result.collected_at
            for result in eligible
            if result.collected_at
        ]
        if not timestamps:
            raise ValueError("Successful collection results must include collected_at")
        collected_at = max(timestamps, key=_parse_collected_at)
        quality_now = _parse_collected_at(collected_at)
        sector_indices = {}
        for sector in SECTOR_KEYS:
            sector_index = compute_sector_index(analyses[sector])
            sector_index["sample_quality"] = compute_sample_quality(
                sector_posts[sector],
                analyses[sector],
                quality_now,
            )
            sector_indices[sector] = sector_index
        source_mode = dominant_source_mode([result.mode for result in eligible])
        history = merge_success(
            history,
            sector_indices,
            collected_at=collected_at,
            source_mode=source_mode,
        )
        save_history(data_dir, history)
    elif not (data_dir / "history.json").exists():
        save_history(data_dir, history)

    market_context = (
        import_snapshot(market_import_path)
        if market_import_path is not None
        else None
    )
    payload = build_payload(
        history,
        source_results,
        market_context=market_context,
    )
    engine = validate_payload(payload)
    write_json(output_path, payload)
    return payload, engine


def _cmd_collect(args: argparse.Namespace) -> int:
    data_dir = _path(args.out)
    results = collect_sources(
        source_names=args.sources,
        allow_simulated=args.allow_simulated,
        data_dir=data_dir,
        xhs_import_path=_path(args.xhs_import) if args.xhs_import else None,
    )
    for result in results:
        errors = f", errors={len(result.errors)}" if result.errors else ""
        print(f"{result.source_id}: mode={result.mode}, posts={result.post_count}{errors}")
    print(f"collection state: {data_dir / 'collection.json'}")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    data_dir = _path(args.data)
    output = _path(args.out) if args.out else data_dir / "dashboard_data.json"
    payload, engine = build_dashboard(
        data_dir,
        output,
        market_import_path=_path(args.market_import) if args.market_import else None,
    )
    print(
        f"dashboard payload: {output} "
        f"(records={payload['record_count']}, stale={payload['freshness']['is_stale']}, validator={engine})"
    )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    payload = _path(args.payload)
    engine = validate_payload_file(payload)
    print(f"valid schema-v3 payload: {payload} ({engine})")
    return 0


def _cmd_all(args: argparse.Namespace) -> int:
    data_dir = _path(args.data)
    collect_sources(
        source_names=args.sources,
        allow_simulated=args.allow_simulated,
        data_dir=data_dir,
        xhs_import_path=_path(args.xhs_import) if args.xhs_import else None,
    )
    output = _path(args.out) if args.out else data_dir / "dashboard_data.json"
    payload, engine = build_dashboard(
        data_dir,
        output,
        market_import_path=_path(args.market_import) if args.market_import else None,
    )
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
    collect.add_argument(
        "--xhs-import",
        metavar="PATH",
        help="local-only sanitized Xiaohongshu JSON/JSONL import",
    )
    collect.add_argument(
        "--out",
        default=str(DEFAULT_DATA_DIR),
        help="data-state directory",
    )
    collect.set_defaults(handler=_cmd_collect)

    build = subparsers.add_parser(
        "build",
        help="update LKG on success and build schema-v3 output",
    )
    build.add_argument("--data", default=str(DEFAULT_DATA_DIR), help="data-state directory")
    build.add_argument(
        "--out",
        help="dashboard JSON path (default: <data>/dashboard_data.json)",
    )
    build.add_argument(
        "--market-import",
        metavar="PATH",
        help="local-only validated market snapshot JSON for this build",
    )
    build.set_defaults(handler=_cmd_build)

    validate = subparsers.add_parser("validate", help="validate a public dashboard payload")
    validate.add_argument("payload", help="path to dashboard JSON")
    validate.set_defaults(handler=_cmd_validate)

    all_command = subparsers.add_parser(
        "all",
        help="collect, build, and validate in one command",
    )
    all_command.add_argument(
        "--sources",
        nargs="+",
        default=["guba"],
        choices=["guba", "xhs-rnote"],
    )
    all_command.add_argument("--allow-simulated", action="store_true")
    all_command.add_argument(
        "--xhs-import",
        metavar="PATH",
        help="local-only sanitized Xiaohongshu JSON/JSONL import",
    )
    all_command.add_argument(
        "--market-import",
        metavar="PATH",
        help="local-only validated market snapshot JSON for this build",
    )
    all_command.add_argument(
        "--data",
        default=str(DEFAULT_DATA_DIR),
        help="data-state directory",
    )
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
