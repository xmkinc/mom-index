All files and the restricted diff have been reviewed. Here is the final read-only release review.

APPROVE_WITH_NOTES

## Findings (severity-ordered)

**1. Low — `check_site.py` no longer hard-fails when `jsonschema` is absent** (`scripts/check_site.py:93`, `mom_index/validation.py:319-322`). The pre-repair `_check_payload` raised a Failure if `jsonschema` was not importable; the repaired version delegates to `validate_payload`, which silently falls back to the built-in bootstrap validator on ImportError. In the Pages workflow the dependency is installed (the rehearsal confirmed the Draft 2020-12 path), and the built-in validator independently enforces every release-critical invariant, so this is environmental hardening loss, not a live gate loss. Not blocking; worth restoring an explicit engine assertion in a future task.

**2. Low — Draft 2020-12 `FORMAT_CHECKER` was dropped from the site check** (`scripts/check_site.py`, removed lines in the diff). The old check_site validator passed `format_checker=...`; `validate_payload` does not. This is offset by `_timezone_aware`, which strictly checks every timestamp field (`generated_at`, `collected_at`, `last_success_at`, `imported_at`, `as_of`) with mandatory timezone info — stricter than JSON Schema `date-time` for the fields that matter — and the unified path *adds* the privacy walk and built-in truth checks that check_site previously lacked. Net strictness increased.

**3. Informational — a v2 payload carrying an unexpected `market_context` would have it replaced, not validated, in the view** (`mom_index/validation.py:97-103`). `_validation_view` unconditionally overwrites `market_context` in the upgraded copy, so a malformed v2-with-market-context payload passes structural validation of that field. It cannot leak secrets (`_walk_public` runs against the original payload, `mom_index/validation.py:315-316`), and by definition v2 does not carry the field, so this is theoretical.

## Criteria assessment

- **Safe v2 support without mutation** — Confirmed. `_validation_view` deep-copies before the additive upgrade (`validation.py:83`); the regression test asserts `payload == original` post-validation (`tests/test_export.py`), and `build_site.py` copies the file byte-for-byte via `shutil.copy2`. The on-disk data branch and input object are untouched.
- **Strict v3 and unknown-version rejection** — Confirmed. Version 3 bypasses the view entirely and runs the unchanged validators; anything other than 2 or 3 raises `PayloadValidationError` (`validation.py:78-81`), and `build_site.py:62-63` rejects unknown versions before any copy. Covered by tests for version 99 in both `test_export.py` and `test_site_compatibility.py`.
- **Privacy/source-truth/secret/artifact/asset gates** — Preserved. `_walk_public` runs on the raw payload for both versions (with an explicit v2 secret-injection test); check_site retains all secret patterns, forbidden-term scans, truthful-source/label checks, stale/market warnings, asset-reference and vendored-Chart.js checks, and now additionally gains the strict validator's checks by reusing it.
- **No drift** — Confirmed within the reviewed scope. The diff touches only the two implementation modules, two scripts, and two test files named in the T-002/T-003 write scopes; no workflow, frontend, schema, scoring, collector, or data-branch files changed, matching the integration report's scope verification. The only user-visible wording change is the truthful `dashboard payload` CLI label, with a test forbidding the old v3-only wording.
- **Sufficient to merge and deploy** — Yes. The design's core requirement — one strict compatibility validator shared by CLI, build, and check, rather than duplicated weaker gates — is implemented exactly (`check_site.py:37,93`), and the immutable rehearsal against the real `origin/data` schema-v2 payload plus the 198-test suite exercises the actual deployment path end to end.

## Release recommendation

Merge and deploy under the existing Pages workflow. The repair is minimal, additive, non-mutating, and matches the D-002@2 decision precisely. The two low-severity notes (explicit `jsonschema` presence assertion in check_site, and optionally rejecting v2 payloads that unexpectedly carry `market_context`) are hardening follow-ups for a post-release task, not release blockers.
