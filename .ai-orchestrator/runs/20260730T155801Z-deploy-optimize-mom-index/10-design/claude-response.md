# Architecture Contract — mom-index deploy & optimize

Run: `20260730T155801Z-deploy-optimize-mom-index` · Revision: R1 (proposed) · Author: Claude/Fable 5 (architect)
Base: `master` @ `0c68a455b60a973c6e31ea7c8c335c868ba346f2`

All required intake, charter, role, and repository files were read in full; no implementation files were modified. The contract is also persisted at `~/.claude/plans/you-are-the-architecture-melodic-frost.md`.

---

## 1. Goals, non-goals, assumptions, unresolved user decisions

### Goals
- **G1**: Reachable GitHub Pages site at `https://xmkinc.github.io/mom-index/` built by a repeatable GitHub Actions workflow.
- **G2**: Unattended scheduled refresh using only unauthenticated public sources (Guba); failures preserve last-known-good (LKG) data and surface visible stale/degraded status; never fabricate a successful update.
- **G3**: Separate collection / analysis / scoring / packaging / presentation into testable modules with one-directional dependencies.
- **G4**: Self-describing public schema (v2): timestamps, per-source provenance and mode (`live` / `simulated` / `unavailable`), freshness, warnings; no credentials, author identities, or unnecessary post content.
- **G5**: Deterministic, documented, tested scoring; fix correctness bugs (parser misalignment, duplicated `interpret`, simulated-history generator, timezone handling, frontend loading-state bug, etc.).
- **G6**: Improved dashboard: mobile-safe layout, vendored Chart.js (no CDN), stale/degraded banner, source-mode badges, loading/error/empty states, plain-language methodology, honest source labels.
- **G7**: Pinned dependencies, CI (pytest + compileall + site smoke + workflow lint), operational docs.
- **G8**: Preserve project spirit and the four sectors (Nasdaq, Gold, CPO, Semiconductor).

### Non-goals
- LLM-based semantic classification (keep the deterministic keyword engine; rename it honestly).
- New data sources (Douyin/Weibo), backtesting, push notifications (WeChat/Telegram).
- Any public automated Xiaohongshu collection — login/paid-API paths stay explicit local-only, disabled by default.
- Server-side backend; i18n; visual redesign beyond required UX states.

### Assumptions
- **A1**: Fork `xmkinc/mom-index` exists (or will be created by user/Codex with authenticated `gh`) with Actions enabled; Pages is enabled *after* the deploy workflow merges (charter release policy).
- **A2**: GitHub Actions runners may or may not reach `guba.eastmoney.com` (geo/WAF unknown). The architecture must deploy successfully either way, showing a degraded state if collection fails — this is the top external risk (R1).
- **A3**: Chinese-language UI is retained (original spirit).
- **A4**: Project site is served under the `/mom-index/` subpath → all asset/data references must be relative.
- **A5**: Python 3.11+ on runners; `requests` (+ `jsonschema`) as pinned runtime deps; Playwright is a local-only optional extra, never installed in CI.

### Unresolved user decisions (safe defaults chosen; none block build)
- **D1**: Existing committed history (31 records, 2026-06-01→06-21, largely simulated, with duplicate dates) — **default: purge from public data; keep as a labeled test fixture**. Alternative: render as a dashed "demo" series.
- **D2**: Refresh cadence — **default: every 6 hours** plus `workflow_dispatch`. Load stays polite (4 list pages per run).
- **D3**: Optional rnote.dev XHS path as a secret-gated workflow input — **default: no; local-only** until a compliant public integration is designed.
- **D4**: Fork/Pages enablement is an account-level action outside repo automation — user (or Codex with `gh` auth) must perform it at release time.

## 2. Current-state observations (grounded in repository files)

- `pipeline.py` — monolithic collect→analyze→score→store→copy. Duplicates `interpret()` (drift risk vs `analyzer/index_calculator.interpret_index`). Its `__main__` **fabricates and saves 30 days of random simulated history** whenever `record_count < 5` (`generate_sample_history`), with buggy date arithmetic at `pipeline.py:129-131` that produces duplicate dates — confirmed: `data/history.json` holds 31 records across only 21 calendar days. It also copies `data/` → `frontend/data/`, leaving two committed copies of the same artifacts.
- `collectors/xhs_collector.py` — with no API key, `collect_all()` **silently returns ~54 hand-written fake posts** (`_gen_sample_posts`, platform `"xiaohongshu"`, fabricated authors) that `pipeline.py:44-46` merges into the index indistinguishably from live data. This directly violates the charter ("never manufacture or silently label simulated data as live"). Hardcoded proxy `127.0.0.1:7890`.
- `collectors/guba_collector.py` — hardcoded `PROXY = 127.0.0.1:7890` (guaranteed failure on CI runners); `parse_posts` runs five independent regexes over the whole page and zips them positionally, so any missing field or filtered title misaligns author/reads/date across rows; no retries; a failure silently yields an empty sector.
- `collectors/xhs_playwright.py` — Windows-only paths (`%LOCALAPPDATA%`), requires login state; correctly not wired into the pipeline; must remain local-only.
- `collectors/anti_detection.py` — UA rotation, human delays, Playwright stealth. The public path needs only header rotation + polite delays; the stealth machinery belongs solely to the local-only XHS path.
- `analyzer/llm_analyzer.py` — misnamed: it is deterministic keyword rules, no LLM. Pure and testable, but intent detection counts binary keyword presence, thresholds/weights are untested, and there is no post dedupe by id.
- `analyzer/index_calculator.py` — deterministic weighted formula, but: inconsistent denominators (`newbie_ratio` over `valid_posts` while the newbie set is drawn from all posts — safe only because spam is forced to score 0); `activity_signal` is computed and displayed yet unused in the index; `buy_sell_ratio` uses `max(sell,1)` so "9 buys / 0 sells" renders as `9.0` while README claims `∞:0`; naive local `datetime.now()` timestamps — on UTC runners the day boundary lands at 08:00 Beijing time.
- `frontend/dashboard.html` — Chart.js from the jsDelivr CDN (violates the charter's "usable when JS dependencies unavailable"; jsDelivr is also unreliable in mainland China); `renderTopPosts` appends via `innerHTML +=`, leaving the "加载中..." spinner visible forever; the footer claims 抖音 (Douyin) as a data source — false; no freshness/stale/source-mode display; the `.charts` grid `minmax(500px,1fr)` overflows viewports between ~500–600px; the entry file is `dashboard.html`, not `index.html`. The data fetch path is correctly relative.
- Repo hygiene — no `requirements.txt`/lock, no tests, no CI, no workflows, no LICENSE file (README says MIT), README claims Python 3.14 vs the charter's 3.11+; both `data/*.json` and `frontend/data/*.json` are committed.

## 3. Proposed architecture

### 3.1 Module layout (target tree)

```
mom_index/                      # Python package, run via `python -m mom_index`
  config.py                     # SECTORS, thresholds, paths, env (MOM_INDEX_PROXY optional, RNODE_API_KEY)
  collectors/
    __init__.py                 # SourceResult / SourceStatus dataclasses; get_public_collectors()
    guba.py                     # public, default-on; row-scoped parsing; retries; per-sector errors
    anti_detection.py           # headers + delays for the public path; stealth stays with local xhs
    xhs_rnote.py                # optional, key-gated, never default; mode="live" only with a real key
    xhs_playwright.py           # local-only; excluded from public pipeline and CI
    simulated.py                # demo fixture posts; only via explicit --allow-simulated; mode="simulated"
  analysis/
    signals.py                  # signal/keyword tables (data only)
    classifier.py               # analyze_post/analyze_all — pure functions, no I/O
    scoring.py                  # compute_sector_index, interpret_index (single source of truth)
  storage.py                    # history load/save, same-day replace, LKG merge, migration
  export.py                     # build v2 payload, strip authors, cap top posts, validate vs schema
  cli.py + __main__.py          # collect | build | validate | all
schema/dashboard.schema.json    # JSON Schema for the public payload
frontend/
  index.html                    # renamed from dashboard.html
  assets/app.js, styles.css, chart.umd.min.js    # vendored Chart.js 4.x (MIT)
  data/                         # BUILD OUTPUT ONLY — gitignored
scripts/build_site.py           # assemble _site/ = frontend/* + data payload
scripts/check_site.py           # site smoke checks (schema, relative paths, labels, no CDN/secrets)
tests/                          # pytest suite + fixtures (guba HTML fixture, demo posts, demo history)
.github/workflows/ci.yml        # PR/push: pytest, compileall, build+check_site, workflow YAML parse
.github/workflows/refresh-data.yml   # cron+dispatch: collect→build→validate→commit to `data` branch
.github/workflows/deploy.yml    # push to master / after refresh: build _site → deploy Pages
requirements.txt / requirements-dev.txt    # pinned
data/history.json               # seed LKG on master; live LKG maintained on the `data` branch
README.md, docs/OPERATIONS.md, LICENSE
```

Removed/absorbed: `pipeline.py` becomes a thin deprecation shim delegating to `python -m mom_index all`; `sync_data.py` deleted (dual-copy eliminated); top-level `analyzer/` and `collectors/` move into the package; `frontend/data/*.json` untracked.

### 3.2 Data flow

```
[refresh-data.yml: cron / dispatch]
  checkout master (code) + data branch → data/
  collect  → per-source SourceResult {posts, mode, collected_at, errors}
  build    → classifier → scoring → storage.merge(LKG) → export v2 payload
  validate → jsonschema check  (failure = no commit, no new-data deploy)
  commit data/ to `data` branch (single writer, concurrency-guarded)
  → triggers deploy.yml

[deploy.yml: push to master | workflow_run(refresh) | dispatch]
  checkout master + data branch → scripts/build_site.py → _site/
  scripts/check_site.py _site   (gate)
  upload-pages-artifact → deploy-pages
```

Collection failure path: collectors return `mode="unavailable"` with error strings; `storage.merge` leaves prior history untouched; `export` derives `freshness.is_stale` from `last_success_at`; build/validate/deploy still succeed and the site shows a degraded banner. If the build itself fails, the workflow fails and the previous Pages deployment stays live — natural rollback.

### 3.3 Public interfaces

CLI (stable contract for workflows and docs):
- `python -m mom_index collect [--sources guba] [--allow-simulated] [--out data/]`
- `python -m mom_index build [--data data/] [--out data/dashboard_data.json]`
- `python -m mom_index validate <payload.json>`
- `python scripts/build_site.py --out _site` · `python scripts/check_site.py _site`

Schema v2 (top-level shape; authoritative copy lives in `schema/dashboard.schema.json`):

```jsonc
{
  "schema_version": 2,
  "generated_at": "2026-07-30T16:00:00+00:00",        // UTC, tz-aware
  "display_timezone": "Asia/Shanghai",                 // day boundary for record dates
  "sources": [
    { "id": "guba", "label": "东方财富股吧", "mode": "live|unavailable",
      "collected_at": "…|null", "post_count": 312, "errors": [] },
    { "id": "xiaohongshu", "label": "小红书", "mode": "unavailable|simulated",
      "collected_at": null, "post_count": 0, "errors": ["…"] }
  ],
  "freshness": { "is_stale": false, "last_success_at": "…", "stale_after_hours": 12 },
  "warnings": [],
  "methodology": { "formula_version": "1.1",
    "weights": {"newbie_ratio":0.40,"newbie_intensity":0.25,"sentiment_extremity":0.20,"purity":0.15} },
  "latest": { "date": "YYYY-MM-DD", "sectors": { "<sector>": {
      "index": 0, "interpretation": "…",
      "details": { /* counts, ratios, mom_buy_index, mom_sell_index, buy_count, sell_count */ },
      "top_newbie_posts": [ { "title": "≤60 chars", "score": 0, "level": "…",
        "reasoning": "…", "intent": "buy|sell|neutral", "key_signals": ["…"],
        "source_url": "https://guba.eastmoney.com/…" } ]    // NO author field; max 5
  }}},
  "sector_history": { "<sector>": [ {"date":"…","index":0,"source_mode":"live|simulated"} ] },
  "record_count": 21
}
```

The frontend additionally computes client-side staleness (`now − generated_at > stale_after_hours`), so a dead scheduler is visible even if the last payload claimed freshness.

### 3.4 Dependency direction

`cli → {collectors, analysis, storage, export} → config`. `analysis` is pure (no I/O, no network). `export` depends on `storage`/`analysis` models and `schema/`. `frontend` depends only on the JSON schema. `scripts` depend on the package CLI; workflows depend on scripts/CLI. No upward or lateral imports (collectors never import analysis; analysis never imports collectors).

## 4. Security, privacy, failure, compatibility, migration, rollback

- **Security**: least-privilege workflows — `ci.yml`: `contents: read`; `deploy.yml`: `contents: read, pages: write, id-token: write`; `refresh-data.yml`: `contents: write` (pushes only to the `data` branch) with a `concurrency` group. No secrets required or referenced by default. `check_site.py` greps the built artifact for token/cookie/secret patterns.
- **Privacy**: the public export strips post authors and follower counts; titles are truncated to ≤60 chars; ≤5 top posts per sector; raw collected posts stay pipeline-internal and are never published; `source_url` is retained as provenance (already-public URLs).
- **Collection ethics/load**: the public path fetches 4 list pages per run at ≤4 runs/day with polite delays; Playwright stealth machinery is excluded from the public path entirely.
- **Failure behavior**: per-source, per-sector error capture; LKG preserved on failure; `is_stale`/`mode` surfaced in payload and UI; an empty-history state renders an explicit "insufficient history" message rather than invented curves; the build hard-fails (blocking new-data deploys) only on schema-invalid output.
- **Compatibility**: `schema_version: 2`; the new frontend reads v2 only — page and payload ship in the same PR, and no external v1 consumers exist. `pipeline.py` remains as a deprecation shim so the documented old invocation still works.
- **Migration** (one-time, in T1): untrack `frontend/data/*` (+ `.gitignore`); replace committed `data/history.json` per D1 (purge simulated records into a test fixture); regenerate `data/dashboard_data.json` as v2; add the LICENSE file README already promises.
- **Rollback**: site — Pages keeps serving the previous deployment on workflow failure; explicit rollback = `workflow_dispatch` deploy from a prior master SHA. Data — `git revert` on the `data` branch, then dispatch a deploy. Code — normal PR revert on master.

## 5. Acceptance criteria & executable verification

1. `python -m pytest` green locally and in CI (classifier, scoring, storage/LKG, export/schema, guba parser fixtures).
2. `python -m compileall mom_index scripts` clean.
3. `collect → build → validate` succeeds with network; with collection forced to fail (env-based injection), the same sequence still emits a schema-valid payload with `guba.mode="unavailable"` and correct staleness — an executable degraded-path test.
4. `build_site.py` + `check_site.py` pass: `index.html` present, only relative refs, every referenced asset exists in `_site/`, no CDN URLs, payload schema-valid, no simulated data labeled live, no secret-like strings.
5. All three workflows parse as YAML in CI and declare least-privilege permissions; the refresh workflow demonstrably distinguishes a real success from failed collection (degraded payload with `unavailable` mode — never a fake success).
6. The dashboard served from `_site/` shows current indices, buy/sell sub-indices, trends, update time, per-source mode badges, a stale banner when applicable, and loading/error/empty states; no false source claims; usable at 375px; cards/status still render if Chart.js fails to load.
7. README/docs contain exact local-run, test, deploy, and troubleshooting steps; simulated data appears nowhere publicly unless explicitly enabled locally, and then always badged.
8. Post-merge release step (outside CI): Pages enabled; `https://xmkinc.github.io/mom-index/` returns the dashboard.

## 6. Task decomposition (dependency-ordered, non-overlapping write scopes)

Order: **T1 → (T2 ∥ T3) → T4**. Allocation follows task shape — Codex takes the architecture-heavy restructure plus protected-path workflows and integration; Kimi takes Python correctness and the test suite; WorkBuddy takes the self-contained frontend/site-check package. No task exists merely to occupy a worker; T2/T3 are the only safely parallel pair.

**T1 — core restructure, schema, storage/export, collector hardening — Codex**
Restructure into `mom_index/` per §3.1 (move classifier/scoring verbatim; behavioral fixes belong to T2); implement `SourceResult`, storage/LKG, export v2 + `schema/dashboard.schema.json`, CLI; harden the guba collector (drop the hardcoded proxy for an optional `MOM_INDEX_PROXY` env, row-scoped parsing, retries, error capture); quarantine simulated posts into `collectors/simulated.py` behind `--allow-simulated`; keep XHS paths key-gated/local-only; perform the §4 data migration; add `requirements*.txt` and LICENSE; leave `pipeline.py` as a shim; delete `sync_data.py`.
- *Write scope*: `mom_index/**`, `schema/**`, `data/**`, `pipeline.py`, `sync_data.py` (delete), `collectors/**` + `analyzer/**` (delete/move), `requirements*.txt`, `.gitignore`, `LICENSE`.
- *Verify*: `compileall`; CLI collect/build/validate end-to-end in both live and forced-failure modes; `validate` on the migrated payload.

**T2 — analysis/scoring correctness + full test suite — Kimi** (after T1)
Within the frozen schema contract: dedupe posts by id; fix intent-keyword counting semantics; make denominators consistent and document spam handling; single `interpret_index`; resolve the unused `activity_signal` (wire it in with a `formula_version` bump, or remove it from details); define an honest `buy_sell_ratio` contract (e.g., null when `sell_count=0`, UI renders "∞"); tz-aware UTC timestamps with an Asia/Shanghai day boundary. Author the full pytest suite, including guba-parser fixtures and export/schema tests. If a fix requires a schema change — stop and report, per repository rules.
- *Write scope*: `mom_index/analysis/**`, `tests/**`.
- *Verify*: `pytest`; `compileall`; `build`+`validate` against fixtures.

**T3 — frontend rebuild + site assembly/smoke checks — WorkBuddy/GLM-5.2** (after T1, parallel with T2)
`frontend/index.html` with split `app.js`/`styles.css`; vendored Chart.js 4.x; consume schema v2: source-mode badges, stale/degraded banner, client-side staleness, Asia/Shanghai update time, loading/error/empty/insufficient-history states, fix the top-posts spinner bug, honest footer (no Douyin), mobile grid fix down to 375px, `<noscript>` notice, plain-language methodology from the `methodology` field. Write `scripts/build_site.py` and `scripts/check_site.py`.
- *Write scope*: `frontend/**`, `scripts/**`.
- *Verify*: `build_site.py` + `check_site.py`; manual smoke via `python -m http.server` against fixture payloads (fresh, stale, degraded, empty).

**T4 — workflows, docs, integration — Codex** (after T2 & T3)
Author `.github/workflows/{ci,refresh-data,deploy}.yml` (protected paths — must be listed in the task manifest) per §3.2/§4; rewrite README (quick start, methodology, honest source table, limits) and `docs/OPERATIONS.md` (cadence, rollback, troubleshooting, Pages enablement); integrate T1–T3 on `ai/<run>/integration`, run all gates, open the PR, request Claude final review.
- *Write scope*: `.github/workflows/**`, `README.md`, `docs/**`.
- *Verify*: the full gate set of §5 items 1–5; YAML parse; end-to-end local `_site` serve.

## 7. Risks & alternatives

- **R1 (high)** — `guba.eastmoney.com` may block GitHub-hosted runner IPs, leaving scheduled refresh permanently degraded. Mitigation: the degraded path is a first-class, honestly-labeled state and the site deploys regardless; retries + realistic headers. If confirmed post-deploy, follow-ups (self-hosted runner, alternate public endpoint) are a new design decision, out of scope now.
- **R2 (med)** — Guba HTML changes silently → zero posts. Mitigation: row-scoped parsing, fixture tests, `post_count`/warnings surfaced; a zero-post live result is flagged as a warning, never treated as a market signal.
- **R3 (med)** — Purged simulated history and the tz day-boundary change make early trend charts sparse. Mitigation: explicit "insufficient history" state; honest accumulation from day one — the charter beats cosmetics.
- **R4 (low)** — `data`-branch races. Mitigation: single writer plus a `concurrency` group; deploy reads at a fixed ref.
- **R5 (low)** — Restructure invalidates the charter's documented check paths. Mitigation: the charter anticipates path adjustment; T4 updates docs and CI to the canonical commands.

**Alternatives considered**: flat layout with minimal moves (rejected — module boundaries/testability are the core ask and the codebase is small enough to move safely in one task); committing refreshed data to `master` (rejected — violates the no-direct-writes release policy and pollutes history); artifact/cache-based LKG (rejected — expiring artifacts cannot guarantee last-known-good); browser-side fetch of Guba (rejected — CORS, integrity, no provenance).

---

DESIGN_READY_WITH_QUESTIONS
