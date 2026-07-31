---
task: T-001
agent: codex
model: GPT-5
status: delivered
branch: ai/20260730T194610Z-fable5-consensus-improvement/codex/T-001
base_commit: 1ef1102f80e313ed00507427354a60e9236ef9a6
commit: a50305fc948d2779883bb90d6ea81e5b145084f0
design_revision: D-002@1
---

# Summary

Scoped ordered compound overrides by source platform. Xiaohongshu retains the
`抄底失败` sell/panic correction; Guba and unknown platforms preserve legacy
ordinary-keyword behavior.

# Changed files

- `mom_index/analysis/signals.py`
- `mom_index/analysis/classifier.py`
- `tests/test_classifier.py`

# Verification

- `python -m pytest -q tests/test_classifier.py tests/test_scoring.py` — 39 passed.
- `python -m pytest -q` — 191 passed.
- `git diff --check` — passed before commit.

# Design decisions

Compound configuration is explicitly keyed by platform and passed into the
existing longest-match masking helper. No scoring or formula code was changed.

# Known risks and limitations

None in task scope. New compound rules for other platforms must be opted in
under their platform key.

# Out-of-scope findings

None.

# Integration recommendation

Cherry-pick commit `a50305fc948d2779883bb90d6ea81e5b145084f0`, rerun the full
suite and site gates, then request Fable 5 final review.
