# T-005 Codex Integration Repair Handoff

- Task: `T-005` — Repair visual balance and Chinese degraded-state copy
- Agent: Codex foreman/integrator
- Design: `D-001@1`
- Branch: `ai/20260730T155801Z-deploy-optimize-mom-index/integration`
- Base SHA: `f06dd24` (integration head before the repair)

## Findings and repairs

Browser visual QA at a 1280px viewport showed the four chart cards in an unbalanced three-plus-one grid. The desktop grid now uses two equal columns; the existing 600px breakpoint still switches to one column. At 375×812, measured document width equals viewport width and no element overflows horizontally.

The honest unavailable state worked, but normal Guba-only output exposed internal English Xiaohongshu and freshness messages in an otherwise Chinese UI. Public default, stale, and simulated warning strings are now Chinese (with the machine-readable word `simulated` retained parenthetically for the existing contract test). The methodology sentence now says the scheduled job reads public pages that do not require login, rather than the ambiguous phrase “公开未授权接口”.

## Verification

- `python -m pytest -q` — 63 passed.
- `python -m compileall -q mom_index scripts tests pipeline.py` — passed.
- `python scripts/build_site.py --out _site` — passed.
- `python scripts/check_site.py _site` — passed.
- `python -m mom_index validate data/dashboard_data.json` — passed with JSON Schema Draft 2020-12.
- `node --check frontend/assets/app.js` — passed.
- Browser desktop live-data QA — four cards, four canvases, eight top posts, no horizontal overflow; chart boxes measured as a two-by-two grid.
- Browser 375px QA — body width 375px, chart grid one column, no horizontal overflow.
- Browser degraded-seed QA — source/freshness warning and methodology copy display in Chinese.

No schema, formula, source policy, workflow behavior, or credential handling changed.
