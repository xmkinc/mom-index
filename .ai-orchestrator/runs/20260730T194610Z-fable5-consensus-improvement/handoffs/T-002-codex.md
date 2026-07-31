---
task: T-002
agent: codex
model: GPT-5
status: delivered
branch: ai/20260730T194610Z-fable5-consensus-improvement/codex/T-002
base_commit: 34f7b632a204f58393c71672e3c1b40983fbc5c8
commit: 2096fbad7174dd909af3aaeaad4bc8a9d81814a0
design_revision: D-002@2
---

# Summary

Added a non-mutating schema-v2 compatibility view that passes legacy public
payloads through the complete strict schema-v3 and privacy validators. Unknown
versions remain rejected.

# Changed files

- `mom_index/validation.py`
- `tests/test_export.py`

# Verification

- `python -m pytest -q tests/test_export.py` — 33 passed.
- `python -m pytest -q` — 194 passed.
- Current `origin/data` v2 dashboard validates with the compatibility view.
- `python -m compileall`, `pip check`, and JavaScript syntax gate passed.
- `git diff --check` passed.

# Design decisions

The original v2 payload and file are never changed. Only a deep-copied,
additive view is validated as v3, retaining strict JSON Schema coverage.

# Known risks and limitations

The site build/check scripts have their own v3-only gates and require a
separate scoped repair before the complete GitHub Pages simulation can pass.

# Out-of-scope findings

The CLI success prefix still says `schema-v3` even when its validator detail
correctly reports use of the legacy-v2 compatibility view.

# Integration recommendation

Cherry-pick `2096fbad7174dd909af3aaeaad4bc8a9d81814a0`, then complete T-003
for build/check and CLI-message compatibility before release.
