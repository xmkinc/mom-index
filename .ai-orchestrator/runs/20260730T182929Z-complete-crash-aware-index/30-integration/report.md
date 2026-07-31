# Final integration report

## Run context

- Run: `20260730T182929Z-complete-crash-aware-index`
- Tasks: `T-001`, `T-002`, `T-003R`, `T-004`, `T-005R`, `T-006`, `T-007`
- Design: `D-001@1`
- Integration owner: Codex
- Branch: `ai/20260730T182929Z-complete-crash-aware-index/integration`
- Accepted base: `0649bdca7003c4ad0cfdbced8f5fa4d97746343f`
- Verified integration head: `9ab7728`
- Status: implementation and executable gates passed; final Claude review remains.

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
- Closed the XHS URL integration discrepancy: exact safe `xiaohongshu.com` and `www.xiaohongshu.com` links are preserved, while HTTP, deceptive subdomains, credentials, explicit ports, whitespace/control characters, and unsafe schemes remain rejected.

## Executable verification

All task commands were run from the task worktree with the repository's pinned Python 3.11 virtual environment placed first on `PATH`.

| Command | Result |
| --- | --- |
| `python -m pytest -q` | PASS — `189 passed in 0.77s` |
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

## Risks and resolved findings

- The XHS bare-host export mismatch found during T-006 was resolved by scoped repair T-007 and 85 focused exporter/importer tests.
- Market snapshots are intentionally local, explicit, and per-build. The public scheduled path therefore exports an honest unavailable market context until a compliant public integration is separately designed.
- WorkBuddy/GLM-5.2 authored the first sanitized-import implementation but its non-interactive bridge could not execute Bash. Codex takeover T-003R reviewed every inherited line, repaired security/type boundaries, and ran the executable gates. The original blocked handoff remains preserved.
- WorkBuddy's frontend task was reassigned as T-005R rather than weakening permission controls. The resulting renderer passed syntax and mocked v2/v3/unknown-version runtime smoke checks; the final site artifact passed `check_site`.
