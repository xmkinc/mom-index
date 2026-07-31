# D-002@2 — Release compatibility repair

## Evidence

The exact GitHub Pages hydration path was reproduced after release approval:
code at the approved integration head plus `data/dashboard_data.json` from
`origin/data`. `python -m mom_index validate data/dashboard_data.json` failed
because the live data branch is schema v2 and does not yet contain the v3
`market_context` field.

## Decision

Restore the accepted backward-compatibility boundary without weakening v3
validation:

1. Validation may accept schema v2 by creating an in-memory additive v3 view
   solely for validation: add unavailable market context, add the legacy
   confidence-model marker, and add null sample quality to latest sectors.
2. Run the existing strict built-in and JSON Schema v3 validators against that
   upgraded view. Privacy scanning remains mandatory.
3. Do not mutate the input object or on-disk data file.
4. Schema v3 remains strictly validated as before; unknown versions remain
   rejected.
5. No scoring, collection, frontend, workflow, credential, or data-branch
   change is authorized by this repair.

This is within the previously accepted requirement to preserve v2 runtime
compatibility and is necessary for the existing data-branch deployment model.
