# T-001 Codex handoff

## Delivery identity

- Task: `T-001` — Define schema v3 and persistence contracts
- Agent/model: Codex (GPT-5)
- Design/spec: `D-001@1`
- Branch: `ai/20260730T182929Z-complete-crash-aware-index/codex/T-001`
- Immutable dispatch base: `ba7b307cc3e453f816d94eab837f5e6a2753f8b9`
- Implementation commit: `f9d3e052622a24a439e0f483ffc36a8d462eb537`
- Commit subject: `feat(schema): define crash-aware v3 contracts`
- Scope verification: passed against the immutable dispatch base with a clean post-commit tree, no out-of-scope files, and all ten delivery files recognized by the task manifest.

## Implemented

- Defined public payload schema v3 with required top-level `market_context`, nullable per-sector `sample_quality`, confidence-model methodology metadata, and `imported` source/history modes while keeping formula version `1.1`.
- Added strict Draft 2020-12 schemas for sanitized Xiaohongshu JSON/JSONL import records and four-sector local market snapshots.
- Added configured A-share market reference symbols/names and schema path/version constants.
- Extended `SourceResult` and persistence contracts for `imported`; added deterministic caveat precedence `simulated > imported > live`.
- Upgraded loaded v2 history additively to v3 and supplied `sample_quality: null` for legacy sector records.
- Exported schema-v3 payloads with fail-closed sample-quality normalization, truthful imported/simulated warnings, normalized available/degraded/unavailable market context, and credential redaction.
- Expanded public privacy validation for identity, profile, session, and credential keys, including camelCase/kebab-case normalization and common secret-token value patterns.
- Added regression coverage for v3 validation, v2 history migration, imported modes, market context normalization/degradation, schema state consistency, boundary schemas, identity rejection, and token redaction.

## Changed files

- `mom_index/collectors/__init__.py`
- `mom_index/config.py`
- `mom_index/export.py`
- `mom_index/storage.py`
- `mom_index/validation.py`
- `schema/dashboard.schema.json`
- `schema/market_snapshot.schema.json`
- `schema/xhs_import.schema.json`
- `tests/test_export.py`
- `tests/test_storage.py`

## Verification commands and results

The host shell did not provide a global `python` command or global pytest/jsonschema packages. The pinned project environment at `/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin` was therefore prepended to `PATH`, after which the task's exact `python ...` commands were executed from this worker worktree.

- `python -m pytest -q tests/test_export.py tests/test_storage.py`
  - Passed: `34 passed in 0.28s`.
- `python -m compileall -q mom_index schema tests`
  - Passed with exit code 0 and no output.
- `python -m pytest -q`
  - Additional full-suite gate passed: `82 passed in 0.36s`.
- Draft 2020-12 `check_schema` over every `schema/*.schema.json`
  - Passed for `dashboard.schema.json`, `market_snapshot.schema.json`, and `xhs_import.schema.json`.
- `git diff --cached --check`
  - Passed with no whitespace errors before commit.
- `agent_orchestrator.py verify-scope --workdir . --base ba7b307cc3e453f816d94eab837f5e6a2753f8b9 --task-file .ai-orchestrator/runs/20260730T182929Z-complete-crash-aware-index/20-tasks/T-001.json`
  - Passed post-commit: `"ok": true`, `"outside_scope": []`, `"working_tree_clean": true`.

## Risks and integration notes

- Downstream tasks must use the exact v3 field names established here: sample quality uses `model_version`, `confidence`, `valid_sample_size`, `title_only_ratio`, `platform_counts`, `classifier_evidence_coverage`, `known_in_window_ratio`, `unknown_time_ratio`, `window_hours`, and ordered `reason_codes`; market returns use keys `1d`, `5d`, and `20d`.
- `build_payload` deliberately degrades absent or invalid market input to an explicit unavailable/degraded context. Market data remains separate from social-index scoring.
- The tracked seed files under `data/**` remain schema v2 because they are outside T-001 `write_scope`. Until T-006 migrates seed output and integration wiring, a site build that validates the existing seed against the new v3 schema is expected to fail.
- CLI wiring, the market loader, the Xiaohongshu importer, sample-quality computation, frontend rendering, documentation, and seed-data migration are intentionally deferred to their dependent tasks.

## Out-of-scope findings

- No unplanned code change was required outside `write_scope`.
- The existing `data/history.json` and `data/dashboard_data.json` require the already-planned T-006 migration; they were not modified here.
- No workflow, scoring-formula, frontend, CLI, architecture, task-manifest, main-branch, deployment, or publication changes were made.
