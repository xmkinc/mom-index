# T-006 integration report

## Run context

- Run: `20260730T182929Z-complete-crash-aware-index`
- Task: `T-006`
- Design: `D-001@1`
- Worker: Codex implementation worker
- Branch: `ai/20260730T182929Z-complete-crash-aware-index/codex/T-006`
- Immutable dispatch base: `f263999dd85aeba18524d21aa923a0656578422d`
- Status: implementation and executable gates passed; commit and final Claude review remain outside this report stage.

## Integrated behavior

- Added explicit local `--xhs-import PATH` support to `collect` and `all`.
- Added explicit local `--market-import PATH` support to `build` and `all`.
- Kept unattended defaults unchanged: `collect` and `all` still default to `--sources guba`, with no imports or simulation enabled.
- Made `imported` source results eligible for complete four-sector LKG updates.
- Applied the declared caveat precedence through `dominant_source_mode`: `simulated > imported > live`.
- Attached deterministic sample-quality output to every newly computed sector record.
- Kept market context outside analysis/scoring and passed it only to public payload construction.
- Migrated the checked-in seed history and public payload from schema v2 to schema v3.
- Hardened public site assembly/checks for schema v3, truthful required labels, explicit imported/simulated caveats, visible stale/market degradation, and the four required renderer concerns.
- Updated README and operations guidance for schema v3, local-only import boundaries, failure semantics, privacy, and market independence.

## Executable verification

All task commands were run from the task worktree with the repository's pinned Python 3.11 virtual environment placed first on `PATH`.

| Command | Result |
| --- | --- |
| `python -m pytest -q` | PASS — `180 passed in 0.57s` |
| `python -m compileall -q mom_index scripts tests pipeline.py` | PASS — exit 0, no output |
| `python scripts/build_site.py --out _site` | PASS — deterministic six-file artifact written |
| `python scripts/check_site.py _site` | PASS — schema, assets, privacy, provenance, and degraded-state checks |
| `node --check frontend/assets/app.js` | PASS — exit 0, no output |
| `python -m pip check` | PASS — no broken requirements |
| Workflow YAML parse smoke | PASS — `workflow yaml: OK` |
| `git diff --check` | PASS — no whitespace errors |

The targeted integration test covers CLI parsing and execution for both import flags, an offline/unavailable Guba source, four-sector imported Xiaohongshu records, available market context, schema-v3 export, and non-null per-sector sample quality. A separate regression proves that adding the market snapshot leaves all four social index values unchanged.

## Scope and protected-path review

- No `.github/workflows/**` file was modified.
- Formula version `1.1`, scoring weights, thresholds, and scoring implementation were not modified.
- All implementation, tests, documentation, seed data, and this report are inside T-006 `write_scope`.
- No merge, push, deployment, publication, or default-branch write was performed.

## Risks and out-of-scope findings

- The schema and XHS importer accept both `xiaohongshu.com` and `www.xiaohongshu.com`, but the read-only public exporter URL allowlist currently accepts only `www.xiaohongshu.com`. A bare-host imported post still contributes to classification/index/quality, but its representative public source link can be omitted. `mom_index/export.py` and its tests are outside T-006 write scope, so this discrepancy was not changed here.
- Market snapshots are intentionally local, explicit, and per-build. The public scheduled path therefore exports an honest unavailable market context until a compliant public integration is separately designed.
- The frontend renderer implementation came from prerequisite T-005R. T-006 verifies its JavaScript syntax and required v3/v2/unknown-version markers, but final responsive browser QA and Claude/Fable design review remain integration-stage responsibilities.
