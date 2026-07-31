# Integration Report — Explainable Sample-Quality Gates

## Identity

- Run: `20260731T165036Z-improve-live-mom-index`
- Accepted design: `D-001@1`
- Integration branch: `ai/20260731T165036Z-improve-live-mom-index/integration`
- Base: `90449c1cd595ab0dc333d15f6964c37b921c800d` (`origin/master` at run creation)
- Worker: Claude Code / Fable 5
- Worker implementation: `e34e1ca35c95a40e130d686b51dd7ef487f05b09`
- Integrated implementation: `a0e8e21`
- Worker handoff: `efd3ef9ea7e4f7aef68a0b30bc0ff950294f2945`
- Integrated handoff: `243933c`

The implementation commit was cherry-picked without content changes. Its integration-branch author metadata was corrected from a stale repository-local worker identity to `Claude Fable 5 <claude-fable-5@ai-orchestrator.local>`; the required `Task`, `Agent`, and `Spec` trailers are intact.

## Integrated behavior

- One canonical tuple now defines all eight currently emittable quality reason codes.
- Sample-quality output adds seven deterministic numeric gates covering the low- and high-confidence sample-size, title-only, evidence-coverage, and in-window thresholds.
- Existing confidence decisions, reason-code logic, formula `1.1`, classifier, scoring, collectors, storage, workflows, and deployment behavior are unchanged.
- Public export admits only a completely valid optional gate list; a malformed list is omitted without discarding the surrounding sample-quality object.
- JSON Schema support is additive and optional, retaining validation for current and legacy/LKG payloads without gates.
- The dashboard maps the real backend reason codes, shows actual-versus-threshold Chinese explanations for quality model `1.0`, falls back safely for legacy or unknown-model payloads, and keeps unknown codes visible.
- CI tests now fail when canonical backend reason codes or emitted gates lack frontend presentation metadata.

## Scope and review

The orchestrator scope verifier compared the task branch with immutable dispatch base `7516b4a17cb8cead9f68f1514ff826dd1d3f87bd` and reported `outside_scope: []`, a clean worktree, and no untracked files. Codex reviewed the implementation diff, schema/export validation, frontend escaping and fallback behavior, and the handoff before integration.

## Independent verification

Codex independently ran the following from the clean task delivery and observed all commands exit 0:

```text
/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -m pip check
  No broken requirements found.

/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -m pytest -q
  237 passed in 1.34s

/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -m compileall -q mom_index scripts tests pipeline.py
  PASS

/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python scripts/build_site.py --out _site
  wrote 6 files

/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python scripts/check_site.py _site
  check_site: OK

/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -c "import pathlib,yaml; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('workflow yaml: OK')"
  workflow yaml: OK

node --check frontend/assets/app.js
  PASS

git diff --check 7516b4a..efd3ef9
  PASS
```

The same full gate set must be rerun from the final integration commit before release recommendation.

## Compatibility, privacy, and rollback

- Gates contain only fixed codes and aggregate numbers; no post text, identities, cookies, credentials, or private logs were added.
- Current payloads without gates remain valid and render through reason-label fallback.
- If a data-branch payload containing gates has been generated and this code is later reverted, regenerate the payload with the reverted code before the next Pages deployment because the former schema rejects unknown sample-quality properties.

## Known risks and deferred work

- The jsonschema-less bootstrap validator does not independently validate the nested gate structure. Export validation plus normal installed JSON Schema validation enforce the contract; defense-in-depth bootstrap validation is deferred because `mom_index/validation.py` was outside T-001 scope.
- Per-sector collection funnels, a privacy-safe classifier evaluation corpus, and new compliant data providers remain separate follow-up waves.
- No push, pull request, merge, deployment, refresh, or publication was performed in this run.
