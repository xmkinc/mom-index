# T-004 Codex Handoff

## Delivery identity

- Task: `T-004` — Add CI, scheduled refresh, Pages deployment, and operations documentation
- Agent/model: Codex implementation worker
- Design revision: `D-001@1`
- Branch: `ai/20260730T155801Z-deploy-optimize-mom-index/T-004-codex`
- Immutable dispatch base: `4463c96b0a8e3fe2c51c4ae06f019eec82edd71d`
- Atomic implementation commit: `d13d85028c4c910ae176df7b4e39e2716ddfd688`
- Commit subject: `feat(operations): automate CI refresh and Pages deploy`
- Commit trailers:
  - `Task: T-004`
  - `Agent: codex`
  - `Spec: D-001@1`

The mandated pre-edit `git status --short` was empty. The pre-edit branch was
`ai/20260730T155801Z-deploy-optimize-mom-index/T-004-codex`, and
`git rev-parse HEAD` exactly matched the immutable dispatch base.

## Outcome

Completed the repository delivery path inside the protected T-004 write scope:

- added read-only CI for pull requests and `master` pushes with Python 3.11,
  pinned dependency installation, `pip check`, pytest, compileall, deterministic
  site build/smoke checks, browser JavaScript syntax checking, and YAML parsing;
- added a six-hour plus manual Guba-only refresh, locked to `master`, with a
  non-cancelling single-writer concurrency group and only `contents: write`;
- made the `data` branch the refresh LKG input/output, copied only
  `history.json` and `dashboard_data.json`, explicitly rejected a persisted
  `collection.json`, and audited the staged path set before every data commit;
- kept collection failure publishable as an honest schema-valid degraded
  payload while relying on the existing build/storage contract to retain LKG
  history;
- added trusted Pages triggers for `master` pushes, successful refresh runs from
  `master`, and explicit manual refs for normal deployment or rollback;
- made each Pages run check out and record concrete code/data commits, hydrate
  only public JSON, validate/build/smoke-check the artifact, and publish through
  the official Pages actions with the accepted permissions and concurrency;
- replaced the obsolete README with accurate Chinese setup, source,
  methodology, architecture, quality-gate, limitation, and deployment
  documentation;
- added a Chinese operations manual for `data`-branch/Pages initialization,
  schedule and manual runs, observability, degraded semantics, troubleshooting,
  rollback without history rewriting, and security controls.

## Changed files

- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `.github/workflows/refresh-data.yml`
- `README.md`
- `docs/OPERATIONS.md`

No Python, schema, data, frontend, script, test, dependency, accepted-design,
task-manifest, or other worker handoff file was changed.

## Verification evidence

Every command in `T-004.json` was run exactly from the worker worktree:

1. `/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -m pytest -q`
   — PASS: `63 passed in 0.20s`.
2. `/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -m compileall -q mom_index scripts tests pipeline.py`
   — PASS: exit 0, no diagnostics.
3. `/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python scripts/build_site.py --out _site`
   — PASS: six deterministic files written, including `index.html`, vendored
   assets, and `data/dashboard_data.json`.
4. `/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python scripts/check_site.py _site`
   — PASS: schema, relative path, asset, source-truthfulness, and secret-pattern
   checks returned `check_site: OK`.
5. `/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -c "import pathlib,yaml; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('workflow yaml: OK')"`
   — PASS: `workflow yaml: OK`.
6. `node --check frontend/assets/app.js`
   — PASS: exit 0, no syntax diagnostics.

Additional delivery checks:

- `git diff --cached --check` — PASS.
- Entire staged diff reviewed — PASS: five expected paths, 676 insertions and
  137 deletions; no unrelated changes.
- Post-commit orchestration scope verifier:
  `agent_orchestrator.py verify-scope --workdir . --base
  4463c96b0a8e3fe2c51c4ae06f019eec82edd71d --task-file
  .ai-orchestrator/runs/20260730T155801Z-deploy-optimize-mom-index/20-tasks/T-004.json`
  — PASS at implementation head
  `d13d85028c4c910ae176df7b4e39e2716ddfd688`, with
  `outside_scope: []`, `untracked: []`, and `working_tree_clean: true`.

## Known risks

- The new GitHub Actions workflows could not execute on GitHub from this worker
  branch because this task expressly forbids push, merge, deploy, and publish.
  Their YAML and every local command they invoke passed, but the integrator must
  observe the first trusted CI/refresh/deploy runs after integration.
- The remote `data` branch must exist with the schema-v2 seed files before a
  refresh or deployment can check it out, and Pages must be configured to use
  GitHub Actions. Exact non-force initialization and Pages steps are recorded in
  `docs/OPERATIONS.md`.
- GitHub-hosted runners may be blocked or rate-limited by Guba. This is accepted
  design risk R1: such a run should still build and deploy an unavailable/stale
  payload while retaining LKG history, but actual runner reachability can only
  be observed after release.
- Repository or branch protection can further restrict the built-in
  `GITHUB_TOKEN`. The refresh requires the declared `contents: write` access to
  the `data` branch; no personal token or secret fallback was added.

## Out-of-scope findings

- No necessary implementation change was discovered outside the T-004 write
  scope.
- Creating or changing the remote `data` branch, enabling Pages, opening or
  merging a PR, pushing `master`, and verifying the public URL are release and
  integration actions. They were intentionally not performed by this worker.
- Claude/Fable final design review and combined integration reporting remain
  the integrator's next stages; this worker did not modify those artifacts.
