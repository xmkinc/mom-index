# T-002 Handoff — Kimi Implementation Worker

- **Task:** T-002 — Correct deterministic scoring and add comprehensive tests
- **Agent:** kimi
- **Branch:** `ai/20260730T155801Z-deploy-optimize-mom-index/T-002-kimi`
- **Base SHA:** `8a8eba36c4bb744b0d6ce5f7ae016ddf44f69d51`
- **Commit SHA:** `48ddc5c8eec771acd61eb6c4aa5835438e207dd7`
- **Spec:** `.ai-orchestrator/runs/20260730T155801Z-deploy-optimize-mom-index/10-design/accepted-design.md` D-001@1

## Changed files

- `mom_index/analysis/classifier.py`
- `mom_index/analysis/scoring.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_classifier.py`
- `tests/test_degraded.py`
- `tests/test_export.py`
- `tests/test_parser.py`
- `tests/test_scoring.py`
- `tests/test_storage.py`
- `tests/test_timezone.py`

## What was implemented

1. **Post deduplication by stable identity**
   - Added `dedupe_posts()` and integrated it into `analyze_sector()` so duplicate `id` values are counted once per sector.
   - Sorting is now deterministic: score descending, then `post_id` ascending.

2. **Correct intent matching**
   - Replaced occurrence counting with unique keyword-set matching to avoid overlapping/substring keyword double counting.
   - Ties (equal buy/sell signal counts) deterministically resolve to `neutral`.

3. **Spam isolation**
   - Spam posts return early with zeroed signals and never enter newbie counts, purity, sentiment, intent, or denominators.
   - `scoring.py` now bases `newbie_posts` and `pure_newbie` on `valid_posts` for consistency.

4. **Honest buy/sell ratio**
   - `buy_count > 0` and `sell_count == 0` → `null`.
   - Both zero → `0.0` (documented deterministic).
   - Otherwise → rounded ratio.

5. **Activity output resolution**
   - `activity` remains a required `details` field per schema v2 but is documented as an independent engagement observation, not part of the weighted index formula.
   - The weighted formula continues to match `config.METHODOLOGY` weights (no config change).

6. **Schema compliance for top posts**
   - Removed non-schema fields `sentiment` and `intent_label` from `top_newbie_posts`.
   - Filter out top posts with empty `source_url` to avoid tripping the schema `oneOf` for `source_url` when format checking is disabled.

7. **Comprehensive pytest suite**
   - `test_classifier.py` — spam, dedupe, intent, newbie scoring, batch analysis.
   - `test_scoring.py` — interpretation boundaries, buy/sell ratio contracts, spam exclusion, formula weights, top-post formatting.
   - `test_parser.py` — Guba row-scoped parser fixtures, alignment, noise filtering.
   - `test_storage.py` — history lifecycle, same-day replacement, missing-sector rejection.
   - `test_export.py` — schema validation, privacy invariants, freshness/staleness, simulation labels.
   - `test_timezone.py` — Asia/Shanghai day boundary for UTC hours.
   - `test_degraded.py` — forced collection failure and unavailable-source payload validation.

## Verification commands and results

```bash
# 1. pytest
/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -m pytest -q
# Result: 63 passed in 0.15s

# 2. compileall
/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -m compileall -q mom_index tests
# Result: compileall OK

# 3. validate committed seed payload
/Users/zilongzhao/Documents/Codex/2026-07-30/ni-k/work/mom-index/.venv/bin/python -m mom_index validate data/dashboard_data.json
# Result: valid schema-v2 payload (jsonschema Draft 2020-12)
```

Additional ad-hoc checks (not in the task manifest) were run to confirm end-to-end behavior:

```bash
# Live collection + build + validate
python -m mom_index collect --sources guba --allow-simulated --out <tmp>
python -m mom_index build --data <tmp> --out <tmp>/dashboard_data.json
python -m mom_index validate <tmp>/dashboard_data.json
# Result: BUILD+VALIDATE OK (records=1, stale=False)

# Forced-failure degraded path
MOM_INDEX_FORCE_COLLECTION_FAILURE=1 python -m mom_index collect --sources guba --out <tmp>
python -m mom_index build --data <tmp> --out <tmp>/dashboard_data.json
python -m mom_index validate <tmp>/dashboard_data.json
# Result: DEGRADED BUILD+VALIDATE OK (records=0, stale=True)
```

## Risks and notes

- **Activity metric not wired into index:** schema v2 requires `activity` in `details` but the `methodology.weights` contract in `config.py` does not include an activity weight. To avoid an undocumented formula change outside this task's write scope, activity is kept as an independent observation. A future task that can update `config.METHODOLOGY` should decide whether to incorporate it.
- **Empty `source_url` workaround:** schema v2's `source_url` uses `oneOf` with `{"const": ""}` and `{"type": "string", "format": "uri"}`. With `jsonschema` format checking disabled by default, empty strings match both branches and fail `oneOf`. Top posts without URLs are therefore excluded. If the schema is revised to `anyOf`, this filter can be removed.
- **No schema/interface changes:** all changes remain inside `mom_index/analysis/**` and `tests/**`; no modifications to schema, storage/export public interfaces, workflows, frontend, or docs.

## Out-of-scope findings

- None required action. The activity-weight question and the `source_url` schema `oneOf` interaction were both handled with in-scope workarounds and are noted above for follow-up.
