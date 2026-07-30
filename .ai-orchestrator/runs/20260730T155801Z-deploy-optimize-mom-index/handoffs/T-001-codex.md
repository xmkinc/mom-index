# T-001 Codex Handoff

## Delivery identity

- Task: `T-001` — Build the truthful public data contract and collection core
- Agent/model: Codex implementation worker
- Design: `D-001@1`
- Branch: `ai/20260730T155801Z-deploy-optimize-mom-index/T-001-codex`
- Immutable dispatch base: `432e291e0b3ed1886b73ecab9d7f49c0e1d18157`
- Implementation commit: `f829623af6c79a89f0a97b310124745f272e564b`
- Commit subject: `feat(core): build truthful public data pipeline`
- Commit trailers:
  - `Task: T-001`
  - `Agent: codex`
  - `Spec: D-001@1`

Pre-edit `git status --short` was empty. The pre-edit branch was the branch above, and
pre-edit `git rev-parse HEAD` exactly matched the immutable dispatch base.

## Outcome

Implemented the T-001 architecture boundary:

- importable `mom_index` package and `python -m mom_index` CLI with `collect`, `build`,
  `validate`, and `all`;
- explicit `SourceResult` states (`live`, `simulated`, `unavailable`);
- unauthenticated Guba collection with row-scoped parsing, retry/backoff, optional
  `MOM_INDEX_PROXY`, polite delays, per-sector errors, zero-row failure detection, and
  `MOM_INDEX_FORCE_COLLECTION_FAILURE` degraded-path injection;
- local-only, API-key-gated rnote/XHS boundary, with no public default registration and
  no simulated fallback;
- explicit-only `--allow-simulated` demo source that is always labeled `simulated`;
- timezone-aware UTC provenance and Asia/Shanghai record-date boundaries;
- atomic collection/history storage, same-day replacement, and LKG preservation when
  collection is unavailable or incomplete;
- schema-v2 privacy-filtered public export with provenance, freshness, warnings,
  methodology, source modes, source links, four-sector history, and no author/raw-post
  fields;
- JSON Schema Draft 2020-12 contract and both JSON Schema validation (when installed)
  and bootstrap/privacy validation;
- honest empty/degraded seed payload and empty v2 history; removed fabricated public
  history and `data/xhs_posts.json`;
- deterministic analysis/scoring moved into the package without T-002 behavior changes;
  the only analysis-result contract addition is `source_url`;
- pinned direct runtime/development dependencies, MIT license, generated-data ignores,
  and a deprecated `pipeline.py` shim; removed `sync_data.py`.

## Changed files

Modified:

- `.gitignore`
- `data/dashboard_data.json`
- `data/history.json`
- `pipeline.py`

Added:

- `LICENSE`
- `mom_index/__init__.py`
- `mom_index/__main__.py`
- `mom_index/config.py`
- `mom_index/cli.py`
- `mom_index/storage.py`
- `mom_index/export.py`
- `mom_index/validation.py`
- `mom_index/analysis/__init__.py`
- `mom_index/analysis/signals.py`
- `mom_index/collectors/__init__.py`
- `mom_index/collectors/anti_detection.py`
- `mom_index/collectors/guba.py`
- `mom_index/collectors/simulated.py`
- `mom_index/collectors/xhs_rnote.py`
- `mom_index/collectors/xhs_playwright.py`
- `schema/dashboard.schema.json`
- `requirements.txt`
- `requirements-dev.txt`

Moved and adapted:

- `analyzer/llm_analyzer.py` → `mom_index/analysis/classifier.py`
- `analyzer/index_calculator.py` → `mom_index/analysis/scoring.py`

Deleted after migration/replacement:

- `collectors/anti_detection.py`
- `collectors/guba_collector.py`
- `collectors/xhs_collector.py`
- `collectors/xhs_playwright.py`
- `data/xhs_posts.json`
- `sync_data.py`

## Verification evidence

The shell had no plain `python` executable. To run the manifest commands literally,
a temporary `/private/tmp` `python` symlink pointed to the available Python 3.11
interpreter (`Python 3.11.15`). No repository file was added for this shim.

Required manifest commands:

- `python -m compileall mom_index pipeline.py` — PASS on Python 3.11.15.
- `python -m mom_index --help` — PASS; all four commands listed.
- `python -m mom_index collect --help` — PASS; source, output, and explicit simulation
  options listed.
- `python -m mom_index build --help` — PASS.
- `python -m mom_index validate data/dashboard_data.json` — PASS; honest seed accepted.
  `jsonschema` was not installed in the worker environment, so this invocation used
  the built-in bootstrap/privacy validator. `jsonschema==4.25.1` is pinned for the
  normal installed path.

Additional executable checks:

- Separate forced-failure `collect → build → validate` sequence — PASS:
  `guba.mode="unavailable"`, `latest=null`, `record_count=0`, stale true, no fabricated
  reading.
- Separate explicit-simulated `collect → build → validate` sequence — PASS:
  one complete four-sector record, `xiaohongshu.mode="simulated"`, timezone-aware LKG,
  simulated history points labeled `simulated`, no author/raw-record keys.
- Complete live fixture through `save_collection → build_dashboard` — PASS:
  `guba.mode="live"`, timezone-aware `last_success_at`, source URLs retained, and
  `2026-07-30T16:30:00+00:00` stored under Shanghai date `2026-07-31`.
- Row-scoped Guba HTML parser fixture with one missing reply field — PASS:
  two rows remained correctly aligned and no author field was emitted.
- Successful explicit-simulated run followed by a forced failed run in the same data
  directory — PASS: one LKG record remained unchanged and visible.
- Old-vs-new deterministic classifier/scorer comparison on newbie, professional, and
  spam fixtures — PASS; output matched after removing only the newly required
  `source_url` field.
- Schema JSON parse and all internal `$ref` resolution assertions — PASS.
- `python3 -m json.tool schema/dashboard.schema.json` — PASS.
- `git diff HEAD --check` before commit — PASS.
- Manual write-scope audit — PASS for all 31 changed paths.
- Post-commit orchestration scope verifier:
  `agent_orchestrator.py verify-scope --base
  432e291e0b3ed1886b73ecab9d7f49c0e1d18157 --task-file .../T-001.json`
  — PASS with `outside_scope: []`, `has_delivery_changes: true`, and clean worktree.

## Known risks

- Live network collection was not exercised because the sandbox has restricted network
  access and the worker Python environment did not have `requests` installed. The
  collector's parser, failure behavior, and complete live-fixture path were exercised.
  GitHub-runner reachability/WAF remains accepted design risk R1.
- The full third-party `jsonschema` execution path was not exercised locally because
  the dependency was absent. The schema parses, all internal references resolve, the
  seed/degraded/simulated/live-fixture payloads pass bootstrap/privacy validation, and
  the exact dependency is pinned.
- T-002 intentionally still owns scoring/classification correctness fixes (dedupe,
  intent semantics, denominator consistency, activity handling, buy/sell infinity
  semantics). T-001 preserved current behavior so those changes remain isolated.
- The Playwright XHS module is now an explicit local-only unavailable boundary rather
  than public automation. The rnote collector remains the functional key-gated local
  path. Neither path was credential-tested, and neither is registered in the public
  collector registry.

## Out-of-scope findings

- The repository still tracks duplicate files under `frontend/data/`:
  `frontend/data/dashboard_data.json`, `frontend/data/history.json`, and
  `frontend/data/xhs_posts.json`. T-001 explicitly forbids frontend changes, so they
  were not deleted or edited. `.gitignore` now prevents future generated
  `frontend/data/` files from being newly tracked, but already tracked copies require a
  T-003/integration-scope deletion.
- Frontend, scripts, workflows, README, and operations documentation were intentionally
  untouched; they belong to T-003/T-004.
- No pytest suite was added because `tests/**` belongs to T-002.

