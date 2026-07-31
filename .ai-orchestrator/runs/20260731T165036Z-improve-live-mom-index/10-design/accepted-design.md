# Accepted Design D-001@1 — Explainable Sample-Quality Gates

## Status and authorship

- Architecture author: Claude/Fable 5
- Adjudicator: Codex
- Verdict: `DESIGN_READY`
- Accepted scope: one end-to-end implementation wave, with no credentials or provider dependency

## Decision

Implement user-facing confidence explanations as the first improvement wave. The current backend emits eight snake_case quality reason codes from `mom_index/analysis/quality.py`, while `frontend/assets/app.js` maps an obsolete uppercase vocabulary. As a result, the live dashboard falls back to raw internal codes precisely where a non-technical reader needs an explanation.

This wave fixes that live trust defect and adds machine-readable evidence for every confidence gate. It outranks a classifier evaluation corpus because the latter is initially internal-only and needs a separate labeling design. It outranks a full collection-funnel diagnostic because that requires a broader collector-to-schema boundary and the current payload already exposes aggregate sample counts, platform counts, source errors, and quality ratios.

## Goals

1. Make every currently emittable quality reason code understandable in Chinese.
2. Expose the actual aggregate value, threshold, comparator, severity level, and pass/fail result for each deterministic quality gate.
3. Render a concise per-sector explanation of why confidence is low or medium without introducing causal, predictive, or fabricated claims.
4. Add an executable drift test so backend codes and frontend labels cannot silently diverge again.
5. Preserve all existing scoring, confidence decisions, privacy rules, LKG behavior, deployment topology, and schema-v2 compatibility.

## Non-goals

- No formula `1.1`, scoring, keyword, classifier, confidence-threshold, or reason-code decision changes.
- No collectors, providers, credentials, APIs, cookies, browser profiles, workflows, refresh cadence, storage, or market-context changes.
- No new dependency, site redesign, or frontend structure rewrite.
- No claim that confidence or the index predicts prices or causes market movement.

## Current-state findings

1. `mom_index/analysis/quality.py` emits: `empty_sample`, `sample_size_below_30`, `sample_size_below_60`, `title_only_ratio_above_0_8`, `title_only_ratio_above_0_4`, `classifier_evidence_coverage_below_0_3`, `classifier_evidence_coverage_below_0_5`, and `known_in_window_ratio_below_0_6`.
2. `frontend/assets/app.js` maps only obsolete uppercase codes such as `LOW_SAMPLE_SIZE` and therefore renders live codes through the raw-code fallback.
3. `tests/test_export.py` uses an obsolete uppercase fixture, and no test checks backend/frontend vocabulary alignment.
4. Thresholds and actual values are not represented together as a machine-readable public contract, allowing documentation and UI text to drift.

## Interfaces and file-level changes

### `mom_index/analysis/quality.py`

Add `CANONICAL_REASON_CODES`, containing the eight existing codes in deterministic order. Extend `compute_sample_quality()` with a `gates` list. Each gate has exactly:

```json
{
  "code": "sample_size_below_30",
  "level": "low",
  "passed": false,
  "actual": 29,
  "threshold": 30,
  "comparator": "gte"
}
```

- `code`: an existing canonical reason-code string.
- `level`: `low` when failure directly forces low confidence, otherwise `high` when it prevents high confidence.
- `passed`: whether the aggregate satisfies the gate.
- `actual` and `threshold`: non-negative finite numbers; sample-size values are integers and ratios are rounded to four decimals.
- `comparator`: `gte` or `lte`, evaluated as `actual >= threshold` or `actual <= threshold`.
- Gate order is fixed and deterministic.
- Existing confidence output and `reason_codes` for an identical input must remain unchanged.

The empty-sample code is canonical but is not a separate numeric threshold gate; the gate array represents numeric sample-size, title-only, evidence-coverage, and known-in-window tests. If implementation chooses to include an empty-sample gate, it must remain machine-readable, deterministic, schema-valid, and must not alter reason-code semantics. The final test suite defines and locks the chosen fixed order.

### `mom_index/export.py`

Extend `_public_sample_quality()` to pass `gates` only when the entire optional list validates:

- exact fields only;
- canonical string code no longer than 80 characters;
- `level` in `low|high`;
- boolean `passed`;
- finite, non-negative `actual` and `threshold` values, excluding booleans;
- `comparator` in `gte|lte`;
- at most 12 gates.

If `gates` is absent, preserve the legacy shape. If present but malformed, omit only `gates`; do not discard an otherwise valid `sample_quality` object.

### `schema/dashboard.schema.json`

Add optional `sample_quality.gates`. It is not required, so existing v3 payloads and migrated schema-v2/LKG records remain valid. Gate items use `additionalProperties: false`, require all six fields, enforce the enums and non-negative numeric constraints, and cap list size at 12.

### `frontend/assets/app.js`

- Replace obsolete `QUALITY_REASON_LABELS` keys with all eight canonical backend codes.
- Continue escaping all dynamic text through `escapeHtml`.
- When a valid `gates` array is available for a known quality model, show failed gates with their actual values and thresholds in plain Chinese.
- When gates are absent or unusable, fall back to labeled `reason_codes`.
- Unknown reason codes remain visibly rendered, never silently hidden.
- Add a short evidence-availability note derived only from payload aggregates such as title-only ratio, platform counts, source modes, and quality fields. Do not infer causes absent from the payload.

### `scripts/check_site.py`

Require a stable UI marker for the new explanation block so a built site cannot accidentally omit it.

### Tests

- `tests/test_quality.py`: lock canonical code order, gate order, values, pass flags, and exact boundary behavior; assert pre-existing confidence and reason-code results remain unchanged.
- `tests/test_export.py`: use a canonical fixture code; test valid gate pass-through, malformed-gate omission, and schema validation with and without gates.
- `tests/test_site_compatibility.py`: extract the frontend reason-label keys and assert they cover `CANONICAL_REASON_CODES`.

### `README.md`

Document the machine-readable gates and the dashboard explanation behavior without changing methodology claims.

## Invariants

- Privacy: gates contain only fixed codes and aggregate numeric values. No post text, author identity, follower data, cookies, credentials, private logs, or bulk raw records are added.
- Honesty: formula, classifier, thresholds, confidence values, and existing reason-code decisions remain identical for identical input.
- Degraded/LKG: legacy records without gates continue to export and render through reason labels. Source availability, staleness, and LKG decisions are unchanged.
- Compatibility: the schema change is additive and optional. The frontend supports payloads both with and without gates.
- Security: no new network access, runtime dependency, secret, HTML trust boundary, or workflow permission.

## Rollback

Revert the integration commit. Because the old schema rejects unknown sample-quality properties, if the `data` branch already contains `gates`, regenerate a gates-free payload with the reverted code before the next Pages deployment.

## Acceptance criteria

1. The backend emits a deterministic gate list with correct thresholds and boundary behavior.
2. All pre-existing sample-quality fields, confidence decisions, and reason codes remain unchanged for identical fixtures.
3. Payloads both with and without gates pass built-in validation and JSON Schema Draft 2020-12 validation.
4. The dashboard has Chinese labels for every canonical reason code and shows actual-versus-threshold explanations when gates are available.
5. Legacy payloads retain a useful fallback; unknown codes remain visible.
6. The backend/frontend drift test fails if a canonical backend code has no frontend label.
7. Full repository quality gates pass.

## Verification

```bash
python -m pip check
python -m pytest -q
python -m compileall -q mom_index scripts tests pipeline.py
python scripts/build_site.py --out _site
python scripts/check_site.py _site
python -c "import pathlib,yaml; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('workflow yaml: OK')"
node --check frontend/assets/app.js
```

## Deferred work

1. Per-sector collection funnel and structured source-health statistics.
2. Privacy-safe deterministic classifier evaluation corpus with precision/recall regression gates.
3. A future quality-model version for unknown-time-specific reason semantics.
4. Compliant provider interfaces for market context and additional platforms after an explicit user/provider decision.
