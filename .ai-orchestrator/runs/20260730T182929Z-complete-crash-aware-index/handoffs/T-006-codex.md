# T-006 Codex handoff

## Identity

- Run: `20260730T182929Z-complete-crash-aware-index`
- Task: `T-006` — Wire CLI, site checks, documentation, and integration
- Agent/model: Codex implementation worker / GPT-5
- Design revision: `D-001@1`
- Actual branch: `ai/20260730T182929Z-complete-crash-aware-index/codex/T-006`
- Immutable dispatch-base SHA: `f263999dd85aeba18524d21aa923a0656578422d`
- Delivered commit SHA: `82bea7670d16b034bd9d978575220cf59e7c898c`
- Commit subject: `feat(integration): wire crash-aware index pipeline`
- Commit trailers:
  - `Task: T-006`
  - `Agent: codex`
  - `Spec: D-001@1`

## Pre-edit verification

- `git status --short` — clean; no output.
- `git branch --show-current` — `ai/20260730T182929Z-complete-crash-aware-index/codex/T-006`.
- `git rev-parse HEAD` — `f263999dd85aeba18524d21aa923a0656578422d`, exactly matching the immutable dispatch base.

## Delivered behavior

- Added explicit local `--xhs-import PATH` support to `collect` and `all`.
- Added explicit per-build `--market-import PATH` support to `build` and `all`.
- Preserved the unattended public default as Guba-only: no local import or simulation flag is enabled by default, and no workflow was changed.
- Included successful `imported` records in complete four-sector builds and used the contract caveat precedence `simulated > imported > live`.
- Attached deterministic sample-quality observations and confidence to every newly computed sector while leaving formula `1.1` unchanged.
- Kept market context independent from analysis/scoring and passed it only to payload export.
- Added CLI-level and regression tests for public defaults, imported LKG/history, per-sector sample quality, end-to-end import flags, and byte-equivalent social index values with/without market context.
- Migrated checked-in seed history and dashboard output to schema v3 with explicit unavailable market context.
- Made the public site builder require a schema-v3 seed and strengthened site smoke checks for truthful required labels, imported/simulated caveats, stale/market warnings, and v3/v2/unknown renderer markers.
- Updated README and operations documentation for schema v3, privacy boundaries, local-only imports, sample-quality gates, market independence, and failure handling.
- Wrote the combined gate report at `.ai-orchestrator/runs/20260730T182929Z-complete-crash-aware-index/30-integration/report.md`.

## Changed files in the atomic commit

- `.ai-orchestrator/runs/20260730T182929Z-complete-crash-aware-index/30-integration/report.md`
- `README.md`
- `data/dashboard_data.json`
- `data/history.json`
- `docs/OPERATIONS.md`
- `mom_index/cli.py`
- `scripts/build_site.py`
- `scripts/check_site.py`
- `tests/test_degraded.py`

The handoff file itself was written after the atomic implementation commit so it could record the actual commit SHA; it is not part of commit `82bea7670d16b034bd9d978575220cf59e7c898c`.

## Verification commands and results

The task worktree initially had no `python` command and the first baseline `python -m pytest -q` attempt returned `zsh: command not found: python`. A task-local venv creation attempt could not download packages because sandbox network access was unavailable. All required commands were then run successfully with the repository's existing pinned Python 3.11 virtual environment first on `PATH`; the command invoked remained `python` exactly as required.

### Required task commands

- `python -m pytest -q`
  - PASS: `180 passed in 0.57s`.
- `python -m compileall -q mom_index scripts tests pipeline.py`
  - PASS: exit 0, no output.
- `python scripts/build_site.py --out _site`
  - PASS: deterministic six-file site artifact written.
- `python scripts/check_site.py _site`
  - PASS: `check_site: OK`.
- `node --check frontend/assets/app.js`
  - PASS: exit 0, no output.

### Additional checks

- `python -m pytest -q tests/test_degraded.py`
  - PASS: `7 passed in 0.24s` before the final full-suite rerun.
- `python -m mom_index build --data data --out data/dashboard_data.json`
  - PASS: generated a schema-v3 seed with zero records, explicit stale state, and unavailable market context.
- `python -m mom_index validate data/dashboard_data.json`
  - PASS: `jsonschema Draft 2020-12`.
- `python -m pip check`
  - PASS: no broken requirements.
- Workflow YAML parse smoke from README/operations quality gates
  - PASS: `workflow yaml: OK`.
- `git diff --check` and `git diff --cached --check`
  - PASS: no whitespace errors.
- Complete unstaged and staged diffs
  - Reviewed in full before commit.
- Scope verifier after the final commit:

  ```text
  python /Users/zilongzhao/.codex/skills/orchestrate-code-agents/scripts/agent_orchestrator.py verify-scope \
    --workdir . \
    --base f263999dd85aeba18524d21aa923a0656578422d \
    --task-file .ai-orchestrator/runs/20260730T182929Z-complete-crash-aware-index/20-tasks/T-006.json
  ```

  - PASS: `ok: true`, head `82bea7670d16b034bd9d978575220cf59e7c898c`, nine committed paths, `outside_scope: []`, and clean before this handoff was written.

## Known risks

- Market context remains intentionally local, explicit, and per-build. The public scheduled path will truthfully show it as unavailable until a separate compliant public market integration is designed.
- Site checks verify the frontend's required concern/degraded markers and JavaScript syntax, but final responsive desktop/mobile visual QA and Claude/Fable design review remain integration-stage work.
- The generated seed timestamp records the actual schema-v3 migration build time (`2026-07-30T19:32:43.977391+00:00`); future public refreshes will replace it normally.

## Out-of-scope findings

- `schema/xhs_import.schema.json` and `mom_index/collectors/xhs_import.py` accept both `xiaohongshu.com` and `www.xiaohongshu.com`, while the read-only allowlist in `mom_index/export.py` currently accepts only `www.xiaohongshu.com`. A bare-host imported post still affects classification, sample quality, and the social index, but its representative public source link can be omitted. Exporter/schema/test changes are outside T-006 `write_scope`, so this discrepancy was recorded rather than changed.
- No `.github/workflows/**`, scoring, formula, schema, frontend, architecture, task manifest, or another worker's handoff file was modified.

## Stop state

- Atomic implementation commit created.
- Handoff written at the required path.
- No merge, cherry-pick, push, deployment, publication, or default-branch write was performed.
