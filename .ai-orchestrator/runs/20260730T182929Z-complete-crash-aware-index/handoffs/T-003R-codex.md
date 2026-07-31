# T-003R Codex takeover handoff

## Delivery identity

- Task: `T-003R` — Review and complete WorkBuddy Xiaohongshu import delivery
- Agent/model: Codex / GPT-5
- Design/spec: `D-001@1`
- Actual branch: `ai/20260730T182929Z-complete-crash-aware-index/workbuddy/T-003`
- Immutable dispatch base: `4bbe1e157513b30b69dc2bfb5c3de3a737debb2c`
- Implementation commit: `6e7b3db712411d0383104115797f9d3429d191a8`
- Commit subject: `feat(import): add sanitized Xiaohongshu boundary`
- Commit trailers:
  - `Task: T-003R`
  - `Agent: codex`
  - `Spec: D-001@1`

The required pre-edit checks showed that HEAD exactly matched the immutable
dispatch base. The worktree already contained the untracked WorkBuddy
implementation, tests, and `T-003-glm52.md` handoff. That prior handoff was read
completely and left untouched.

## Changed files

- `mom_index/collectors/xhs_import.py`
- `tests/test_xhs_import.py`

No architecture, task manifest, workflow, public collector, configuration,
schema, CLI, another worker's handoff, or default branch was modified.

## Review and repairs

Every inherited implementation and test line was reviewed. The takeover:

- retained JSON-array, per-sector JSON-map, and JSONL import support;
- retained explicit per-record rejection and unavailable-on-zero-valid behavior;
- retained `SourceResult(mode="imported")`, per-sector post grouping, stable
  public fields, and truthful Xiaohongshu platform labeling;
- retained fail-closed rejection of identity, credential, session, profile, and
  secret-like data;
- fixed schema conformance by rejecting non-string `id`, `title`, `content`,
  `url`, and `sector` values instead of coercing them with `str(...)`;
- moved privacy scanning ahead of ordinary schema rejection and made it
  iterative, so nested private keys, secret-like values in otherwise-invalid
  records, and secret-like scalar records abort the entire import;
- strengthened URL validation to require HTTPS, an exact allowed Xiaohongshu
  host, no user information or port, a path, and no whitespace/control
  characters;
- made invalid UTF-8 and excessive JSON nesting degrade to unavailable instead
  of escaping the importer contract;
- stopped missing/unreadable-file errors from reproducing local filesystem
  paths;
- removed an invalid inherited test that expected constructing an exception
  object to raise itself, and replaced it with behavioral fail-closed tests.

## Verification commands and results

### Required pre-edit Git checks

- `git status --short`
  - Showed only the three inherited untracked WorkBuddy files:
    `T-003-glm52.md`, `mom_index/collectors/xhs_import.py`, and
    `tests/test_xhs_import.py`.
- `git branch --show-current`
  - `ai/20260730T182929Z-complete-crash-aware-index/workbuddy/T-003`
- `git rev-parse HEAD`
  - `4bbe1e157513b30b69dc2bfb5c3de3a737debb2c` — exact match.

### Tests and static checks

- `python -m pytest -q tests/test_xhs_import.py`
  - Initial direct run: **environment failure**, `python: command not found`.
  - Re-run with the available repository dependency environment on `PATH`:
    **55 passed in 0.08s**.
- Baseline inherited suite through the available virtualenv:
  - **45 passed, 1 failed**. The sole failure was the invalid exception
    construction test described above.
- `python -m pytest -q`
  - Run with the same available dependency environment on `PATH`.
  - **137 passed in 0.45s**.
- `python -m compileall -q mom_index/collectors/xhs_import.py tests/test_xhs_import.py`
  - Exit 0; no output.
- `git diff --no-index --check -- /dev/null mom_index/collectors/xhs_import.py`
  - Exit indicated a new-file diff only; no whitespace errors.
- `git diff --no-index --check -- /dev/null tests/test_xhs_import.py`
  - Exit indicated a new-file diff only; no whitespace errors.
- `git diff --check 4bbe1e157513b30b69dc2bfb5c3de3a737debb2c..6e7b3db712411d0383104115797f9d3429d191a8`
  - Exit 0; no output.
- Whole-diff review
  - Reviewed all 379 importer lines and all 468 test lines before commit.

### Scope verification

Command:

```text
python3 /Users/zilongzhao/.codex/skills/orchestrate-code-agents/scripts/agent_orchestrator.py verify-scope --workdir "$PWD" --base 4bbe1e157513b30b69dc2bfb5c3de3a737debb2c --task-file .ai-orchestrator/runs/20260730T182929Z-complete-crash-aware-index/20-tasks/T-003R.json
```

Result: the verifier reported `ok: false` because the inherited untracked
`.ai-orchestrator/runs/20260730T182929Z-complete-crash-aware-index/handoffs/T-003-glm52.md`
is not covered by T-003R's automatic handoff allowance. The same verifier
reported that the commit's complete changed-file set is exactly:

- `mom_index/collectors/xhs_import.py`
- `tests/test_xhs_import.py`

The inherited WorkBuddy handoff was not edited, staged, committed, removed, or
moved. Manual committed-diff scope verification with
`git diff --name-only <base>..<commit>` confirms no implementation change
outside `write_scope`.

## Known risks

- Import files are read into memory as a whole; the accepted design and task do
  not specify a byte-size or record-count limit.
- A syntactically malformed JSONL line makes the complete file unavailable.
  Decodable records with ordinary schema errors remain explicit per-record
  rejections, while any privacy/credential finding aborts the complete import.
- This task implements and tests the import boundary only. CLI wiring and
  dashboard eligibility for `mode="imported"` remain integration work assigned
  outside T-003R.

## Out-of-scope findings

- The inherited `T-003-glm52.md` handoff remains untracked and causes the
  repository scope verifier's dirty-tree/outside-scope finding for T-003R. It
  belongs to the prior worker and was deliberately preserved.
- `schema/xhs_import.schema.json` and this importer allow both
  `xiaohongshu.com` and `www.xiaohongshu.com`, while the current read-only
  `mom_index/export.py` post-host allowlist appears to include only
  `www.xiaohongshu.com`. Integration should confirm whether bare-host imported
  URLs must remain visible in the public payload; no out-of-scope export change
  was attempted.
- No merge, integration-branch update, push, deployment, or publication was
  performed.
