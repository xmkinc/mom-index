# Handoff — T-001 Explainable Sample-Quality Gates

- **Task**: T-001
- **Agent/Model**: Claude Code / Fable 5 (`claude-fable-5`)
- **Design revision**: D-001@1
- **Branch**: `ai/20260731T165036Z-improve-live-mom-index/T-001-claude`
- **Dispatch base SHA**: `7516b4a17cb8cead9f68f1514ff826dd1d3f87bd` (verified clean and exact before editing)
- **Implementation commit**: `e34e1ca35c95a40e130d686b51dd7ef487f05b09`

## Changed files (implementation commit)

| File | Change |
| --- | --- |
| `mom_index/analysis/quality.py` | Added `CANONICAL_REASON_CODES` (eight codes, fixed order) and an additive `gates` list of seven numeric gates in a fixed order. `passed` is evaluated on the same unrounded aggregates as the existing confidence/reason-code decisions; `actual` reports sample sizes as integers and ratios rounded to four decimals. `empty_sample` remains canonical with no fabricated numeric gate. No change to any pre-existing output field. |
| `mom_index/export.py` | New `_public_gates()`: `gates` passes through only when the entire optional list validates (exact six fields; code non-empty string ≤80; `level` in `low|high`; boolean `passed`; finite non-negative non-bool `actual`/`threshold`; `comparator` in `gte|lte`; ≤12 items). Malformed lists are omitted; the remaining `sample_quality` object is preserved. Absent `gates` keeps the byte-identical legacy shape. |
| `schema/dashboard.schema.json` | Optional `sample_quality.gates` (maxItems 12) with a `qualityGate` def: `additionalProperties: false`, all six fields required, enums and `minimum: 0` numeric constraints. Payloads without gates remain valid (additive change). |
| `frontend/assets/app.js` | `QUALITY_REASON_LABELS` re-keyed to all eight canonical backend codes (escaped Chinese labels). New: prototype-safe `hasOwn` lookups, `validGates` (frontend-side strict gate validation), `gateLineHtml` (failed-gate actual-vs-threshold text with low/high phrasing), `qualityExplanationHtml` (gates view for known model `1.0`, reason-code fallback otherwise), and an evidence-availability note built only from public aggregates (platform counts, title-only ratio, unknown-time ratio). Unknown reason codes and unknown gate codes stay visibly rendered. All dynamic text goes through `escapeHtml`. |
| `scripts/check_site.py` | Requires stable UI markers `quality-explanation` and `质量门槛说明` in the built `assets/app.js`. |
| `tests/test_quality.py` | Locks canonical vocabulary/order, gate order/shape, exact gate values for a high-confidence fixture, `empty_sample` numeric-gate exclusion, exact boundary behavior at 29/30/59/60 samples and ratios 0.8/0.4/0.3/0.5/0.6, and asserts pre-existing fields (confidence, reason_codes, ratios) are unchanged besides the additive `gates` key. Uses synthetic results for exact aggregate control. |
| `tests/test_export.py` | Fixture reason code migrated to canonical `sample_size_below_60`; fixture now carries gates. New `TestQualityGatesExport`: valid pass-through, absent-gates legacy shape, 17 malformed-gate variants omitted without discarding `sample_quality`, 12-gate maximum, empty-list pass-through, JSON-Schema rejection of malformed gate items, and an end-to-end `compute_sample_quality` → export → validate round trip. |
| `tests/test_site_compatibility.py` | Backend/frontend drift gates: `test_frontend_labels_cover_canonical_reason_codes` fails if any `CANONICAL_REASON_CODES` entry lacks a `QUALITY_REASON_LABELS` key; `test_frontend_gate_text_covers_backend_gate_codes` fails if an emitted gate code lacks `QUALITY_GATE_TEXT` metadata or leaves the canonical vocabulary. |
| `README.md` | Documents the machine-readable gates contract (fields, comparator semantics, rounding, 12-item cap, `empty_sample` exception), the additive/fallback behavior, and the dashboard explanation behavior. No methodology-claim change. |

## Verification (all run from the task worktree with `/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python`)

| Command | Result |
| --- | --- |
| `git status --short` / `git branch --show-current` / `git rev-parse HEAD` | clean; correct branch; HEAD == `7516b4a…` before editing |
| `python -m pip check` | `No broken requirements found.` |
| `python -m pytest -q` | `237 passed in 1.42s` (0 failures; suite grew from 200 to 237) |
| `python -m compileall -q mom_index scripts tests pipeline.py` | OK (exit 0) |
| `python scripts/build_site.py --out _site` | wrote 6 files |
| `python scripts/check_site.py _site` | `check_site: OK` (including new quality-explanation markers) |
| workflow YAML parse one-liner | `workflow yaml: OK` |
| `node --check frontend/assets/app.js` | OK |
| `git diff --check` | no whitespace errors |
| Ad-hoc node runtime smoke (stubbed DOM/fetch, payload with gates) | 9/9 PASS: marker present, count-gate and ratio-gate actual-vs-threshold text, high-gate phrasing, evidence note, legacy reason-label fallback, unknown code visible, malformed gates fall back without crash, output escaped |

## Behavior-preservation notes

- `confidence` and `reason_codes` are produced by the exact same untouched code paths; `gates` is appended as a new key only. `tests/test_quality.py::test_existing_fields_are_unchanged_besides_additive_gates` locks the full non-gate output dict for a fixture, and all pre-existing quality/export/degraded tests pass unmodified except the export fixture's obsolete uppercase reason code, which the accepted design explicitly required migrating to a canonical code.
- Gate `passed` flags are evaluated on unrounded aggregates — identical inputs can never yield a gate verdict that contradicts the emitted reason codes; `actual` reports the same 4-decimal rounding as the existing public ratio fields.

## Compatibility / rollback

- Schema change is additive and optional: existing v3 payloads, migrated v2/LKG history records, and the currently committed `data/dashboard_data.json` (no gates) all validate; `tests/test_site_compatibility.py` builds and checks both v2 and v3 sites.
- The frontend renders three payload generations: gates present (explanation view), quality without gates (canonical reason-label fallback), and v2/no-quality (existing unavailable states).
- History records written after this change will carry `gates` inside `sample_quality` (storage passes the dict through verbatim); the dashboard payload validator accepts it. Per the accepted design's rollback note: if the `data` branch ever contains gates and the integration commit is reverted, regenerate a gates-free payload with the reverted code before the next Pages deployment, because the old schema rejects unknown `sample_quality` properties.
- Privacy: gates contain only fixed code strings and aggregate numeric values; no new fields from posts or authors. `validate_payload`'s banned-key/secret scans run over the payload including gates.

## Risks

- The drift tests read `QUALITY_REASON_LABELS` / `QUALITY_GATE_TEXT` from `app.js` with a regex anchored to the current `var NAME = { ... };` two-space-indent formatting. Reformatting those literals (e.g. minification of `frontend/assets/app.js` in-repo) would fail the test loudly (assert on missing match), not silently pass — acceptable but worth knowing.
- Frontend gate rendering is gated on `KNOWN_QUALITY_MODELS = {"1.0"}`. A future `CONFIDENCE_MODEL_VERSION` bump will intentionally fall back to reason-code labels until the frontend map is extended; the drift test on labels still protects the fallback.
- Export-layer gate `code` validation checks shape (non-empty string ≤80 chars, matching the JSON Schema) rather than membership in `CANONICAL_REASON_CODES`, so a hypothetical future backend code passes through; the frontend renders unknown gate codes visibly with raw evidence. This matches the design's schema constraints and keeps export/schema aligned.

## Out-of-scope findings (not changed)

- `mom_index/validation.py` (read-only for this task) performs no built-in structural validation of `gates`; strict gate validation lives in the export layer and the JSON Schema (which `validate_payload` applies when `jsonschema` is installed). If a defense-in-depth built-in check is wanted for the jsonschema-less bootstrap path, that is a follow-up task touching a protected file.
- `docs/OPERATIONS.md` mentions rollback flows generally; it was not in `write_scope`, so the gates-specific rollback caveat is recorded here and in the accepted design rather than in the ops manual.

## Explicitly not done (per manifest)

No merge, push, deploy, publish, integration-branch modification, workflow edits, or changes to collectors/providers/storage/CLI/scoring/classifier/thresholds.
