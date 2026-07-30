# T-004 Handoff — Kimi Worker

## Task

- **Task ID:** T-004
- **Title:** Implement market context snapshot boundary
- **Owner:** kimi
- **Design revision:** D-001@1
- **Agent/model:** Kimi Code CLI

## Branch and base

- **Branch:** `ai/20260730T182929Z-complete-crash-aware-index/kimi/T-004`
- **Base SHA:** `2e29e5e1384b303ad3ddbb4619833b1260aa3126`
- **Commit SHA:** `2c77b57aacf9b13e297511f8fff8043c98370d7b`

## Changed files

- `mom_index/market/__init__.py` (new)
- `tests/test_market_context.py` (new)

## Implementation summary

Implemented the market snapshot validation/import/load boundary inside `mom_index/market/__init__.py`:

- `validate_snapshot(value)` — strict, deterministic validation of schema version, provider, timezone-aware `imported_at`, configured sectors, reference symbol/name, timezone-aware `as_of`, and any non-empty subset of `1d`/`5d`/`20d` window returns. Raises `MarketSnapshotError` on contract violations.
- `load_snapshot(path)` — reads JSON from a file and validates it. Raises `MarketSnapshotNotFoundError` for missing files and `MarketSnapshotError` for JSON/contract failures.
- `import_snapshot(path)` — fail-closed entry point for CLI wiring. Returns an unavailable context with a stable reason code and human-readable error instead of propagating exceptions.
- `unavailable_snapshot(*errors)` / `degraded_snapshot(snapshot, *errors)` — helpers for honest degraded states.

The module imports only `mom_index.config` and intentionally does not import any analysis or scoring code, per the task manifest.

## Verification commands and results

```bash
.venv/bin/python -m pytest -q tests/test_market_context.py
```

Result: `26 passed in 0.03s`

```bash
.venv/bin/python -m compileall mom_index collectors pipeline.py
```

Result: success (no syntax/import errors).

```bash
.venv/bin/python -m pytest -q
```

Result: `121 passed in 0.56s`

## Known risks

- The new module defines its own stable reason codes in `_SnapshotReason`. These are not yet consumed by `export.py` or the dashboard; they exist to support future diagnostics.
- `import_snapshot` normalizes timestamps to UTC ISO strings so the result is JSON-serializable, matching the contract expected by `mom_index.export._public_market_context`.
- The module does not use `jsonschema` directly; validation is implemented in pure Python to guarantee deterministic error messages and behavior without relying on optional format checkers.

## Out-of-scope findings

- No CLI wiring for `--market-import` was added; that remains a downstream integration task.
- No changes were made to `mom_index/export.py`, `mom_index/storage.py`, `mom_index/validation.py`, schema files, the frontend, or GitHub Actions workflows.
- No live network collection was implemented.
- A local `.venv/` was created to install pinned dependencies and run tests; it is untracked and not part of the commit.
