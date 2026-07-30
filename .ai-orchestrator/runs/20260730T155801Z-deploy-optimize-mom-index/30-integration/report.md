# Integration Verification Report

Run: `20260730T155801Z-deploy-optimize-mom-index`  
Design: `D-001@1`  
Integration branch: `ai/20260730T155801Z-deploy-optimize-mom-index/integration`  
Reviewed head: `09f607e8281571a0c9b34823887849c43122f477`

## Integrated outcome

The original one-commit prototype is now a deployable static GitHub Pages application with:

- a versioned schema-v2 public payload and explicit `live` / `simulated` / `unavailable` source modes;
- an unauthenticated, row-scoped Guba collector with retry/backoff, optional proxy, zero-row failure detection, and no hard-coded local proxy;
- local-only, explicit Xiaohongshu boundaries with no simulated public fallback;
- atomic last-known-good history, Asia/Shanghai record boundaries, privacy-filtered export, and schema validation;
- deterministic classifier/scoring fixes, stable post deduplication, spam isolation, honest buy/sell ratio semantics, and one canonical interpretation function;
- a responsive Chinese schema-v2 dashboard with vendored Chart.js, source/freshness badges, degraded/empty/error/chart-fallback states, safe public links, and a balanced desktop/mobile layout;
- deterministic static-site build/smoke tooling;
- CI, a six-hour Guba-only refresh using a single-writer `data` branch, and GitHub Pages deployment from trusted `master` code plus public data state;
- Chinese developer and operations documentation, rollback instructions, and least-privilege workflow permissions.

The original fabricated public history and silently simulated Xiaohongshu posts were removed. The committed seed is intentionally empty/degraded until the first successful public refresh.

## Worker deliveries and scope gates

| Task | Worker | Result |
| --- | --- | --- |
| T-001 core/schema/collector/storage/export | Codex | scope verifier passed; 31 implementation paths, none outside scope |
| T-002 scoring/tests | Kimi | scope verifier passed; 63 tests; none outside scope |
| T-003 dashboard/site tooling | WorkBuddy GLM-5.2 | scope verifier passed; build/smoke/JS checks; none outside scope |
| T-004 CI/refresh/deploy/docs | Codex | scope verifier passed; protected paths exactly declared; none outside scope |
| T-005 visual/copy repair | Codex integrator | browser-QA findings repaired without schema, scoring, source-policy, or workflow changes |

All handoffs are tracked under `handoffs/`. Each implementation was diff-reviewed before cherry-pick, and combined checks were rerun after each dependency cluster.

## Final executable evidence

- Python runtime: local Python 3.11 virtual environment using pinned `requirements-dev.txt`.
- `python -m pytest -q`: **63 passed**.
- `python -m compileall -q mom_index scripts tests pipeline.py`: passed.
- `python -m mom_index validate data/dashboard_data.json`: passed with JSON Schema Draft 2020-12.
- Forced-failure `collect → build → validate`: passed; `guba.mode=unavailable`, `latest=null`, `record_count=0`, `is_stale=true`, no fabricated reading.
- Successful public Guba probe: collected **296 posts across all four sectors**, generated one schema-valid fresh record, and kept Xiaohongshu unavailable.
- A later public probe returned zero valid rows for all four boards: the pipeline stayed green, produced an honest unavailable/degraded payload, and preserved the empty/LKG contract. This reproduces accepted risk R1/R2 and validates the release fallback rather than hiding source volatility.
- `python scripts/build_site.py --out _site`: six deterministic public files.
- `python scripts/check_site.py _site`: passed schema, relative assets, vendored runtime, truthful source, forbidden-term, and secret-pattern gates.
- `node --check frontend/assets/app.js`: passed.
- All `.github/workflows/*.yml` parse with PyYAML; `pip check` reports no broken requirements.
- Git worktree is clean except the tracked run-state/report changes prepared for this report.

## Browser visual evidence

- Degraded seed: Chinese unavailable badges, stale/degraded banner, no invented index cards or curves, methodology and source footer still usable.
- Live fixture: four sector cards, four Chart.js canvases, eight representative posts, live Guba badge, unavailable Xiaohongshu badge.
- Desktop 1280px: chart boxes measure as a balanced two-by-two grid (`577px 577px` columns); document width equals viewport width.
- Mobile 375×812: one chart column (`351px`), document width exactly `375px`, and no element crosses the viewport edge.
- Post loading state is replaced after success/error; safe external links carry `noopener noreferrer nofollow`.

## Security and release checks

- CI: `contents: read` only; no `pull_request_target`.
- Refresh: `contents: write` only; trusted `master` workflow, non-cancelling single-writer concurrency, Guba-only collection, staged-path allowlist, and no `collection.json` persistence.
- Deploy: `contents: read`, `pages: write`, `id-token: write`; trusted code ref and independent data ref; validation and site checks occur before Pages artifact upload.
- No personal tokens, cookies, credentials, browser profiles, raw posts, or author identities are committed or published.
- Runtime dashboard has no CDN dependencies or analytics.

## Remaining release-time observations

- Remote GitHub Actions behavior and Pages reachability must be observed after the reviewed branch is merged.
- The remote `data` branch must be initialized from the schema-v2 `master` seed before refresh/deploy.
- Public Guba availability is externally variable. A green refresh can legitimately represent a schema-valid degraded state; real source success must be determined from `sources[].mode`, not workflow color alone.
- The site will begin with sparse history. This is intentional and preferable to retaining fabricated demo history.

The integrated implementation is ready for Claude/Fable design-conformance review.
