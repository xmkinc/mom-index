---
task: T-003
agent: codex
model: GPT-5
status: delivered
branch: ai/20260730T194610Z-fable5-consensus-improvement/codex/T-003
base_commit: 5a3c96b4b364a1010f6bc098340ddbd547ce09fa
commit: ad3849177a677cd9953f2bf25b958a894330a4a4
design_revision: D-002@2
---

# Summary

Completed the schema-v2 release bridge across static-site build/check and
truthful CLI output. Site smoke checks now reuse the strict compatibility
validator instead of maintaining a separate v3-only schema path.

# Changed files

- `scripts/build_site.py`
- `scripts/check_site.py`
- `mom_index/cli.py`
- `tests/test_site_compatibility.py`

# Verification

- Focused site/export tests: 37 passed.
- Full suite: 198 passed.
- Compile and JavaScript syntax gates passed.
- Exact release simulation using code from commit plus current `origin/data`:
  validate passed, six-file site build passed, check_site passed, and
  JavaScript syntax passed.
- `git diff --check` passed.

# Design decisions

Build accepts only versions 2 and 3. Check-site delegates schema and privacy
validation to `mom_index.validation`, then retains its artifact, source-truth,
asset, secret, and forbidden-term gates.

# Known risks and limitations

The deployed data remains schema v2 until the first successful refresh under
the new schema-v3 code. The frontend deliberately renders the explicit legacy
badge during that transition.

# Out-of-scope findings

None.

# Integration recommendation

Cherry-pick `ad3849177a677cd9953f2bf25b958a894330a4a4`, rerun the full suite
and exact data-branch hydration, then request a fresh Fable 5 release review.
