# D-001@1 — Crash-aware, confidence-explicit Mom Index v0.2

## Goals and invariants

1. Extend the deterministic classifier with Xiaohongshu-scoped vocabulary for help/questions, entry/chasing, position size, loss/recovery, panic/exit, and family/novice framing. Guba matching and numeric behavior must remain unchanged.
2. Add per-sector sample quality derived from observables: valid sample size, title-only ratio, platform counts, classifier-evidence coverage, 72-hour in-window ratio, and unknown-time ratio. Derive high/medium/low confidence from documented gates and ordered reason codes.
3. Add market context for the four sectors with configured reference symbols, 1d/5d/20d returns, as-of timestamps, provenance, and unavailable/degraded states. Market context must never flow into `compute_sector_index`; formula version remains 1.1.
4. Add a fail-closed local sanitized Xiaohongshu JSON/JSONL import boundary. Accept only stable id, title, content, URL, sector, published time, and collection time. Reject identity/credential keys and secret-like values. Never store cookies, browser profiles, authors, followers, or private state.
5. Keep public Actions Guba-only and unauthenticated. Do not modify `.github/workflows/**`.
6. Present four separate concepts in the UI: social index, buy/sell language evidence, sample quality, and market context. Remove bottom calls, position advice, and causal/predictive wording.
7. Bump the public payload to schema v3. The frontend fully renders v3, visibly degrades for v2, and deliberately rejects unknown versions. Existing v2 history remains readable.

## Architecture and dependency direction

- `mom_index/analysis/signals.py` holds platform extensions and bounded compound overrides.
- `classifier.py` consumes signal data and emits additive evidence fields. `quality.py` is a new pure sample-quality module.
- `mom_index/market/__init__.py` validates/imports/loads sanitized market snapshots without importing analysis code.
- `mom_index/collectors/xhs_import.py` converts local sanitized files into `SourceResult(mode="imported")`.
- `storage.py`, `export.py`, `validation.py`, and schema files define additive v3 contracts and v2-history migration.
- `cli.py` wires explicit `--xhs-import` and `market-import` entry points.
- Frontend consumes payload only. No new network or runtime dependency is introduced.

Dependency direction remains: config/data tables → pure analysis; collectors/market boundaries → CLI; storage/export → validated plain dictionaries; frontend → public payload. Analysis never imports collectors or market code.

## Classifier contract

- Apply `PLATFORM_KEYWORD_EXTENSIONS` only when `post.platform` matches; Guba has no extensions.
- Cover at minimum: 怎么办、不会选股、求带、现在入局还不晚、入局、还来得及吗、快跑、逃命、跑不跑、带娃、家庭主妇、上班族、满仓、重仓、三倍做多、加杠杆、抄底失败、回本、被套了、补仓摊平.
- Evaluate ordered longest-match compound overrides before ordinary intent/sentiment matches. `抄底失败` must be panic/sell-side evidence and suppress its inner `抄底` buy/greed match.
- Add only `has_content` and `matched_extension_signals` to `AnalysisResult`; existing fields keep their meanings.
- `compute_sector_index` numerics, thresholds, and weights are frozen. Only descriptive interpretation text changes.

## Quality contract

`compute_sample_quality(posts, results, now, window_hours=72)` is total and deterministic. Low confidence applies when sample size <30, title-only ratio >0.8, or evidence coverage <0.3. High requires sample size ≥60, title-only ratio ≤0.4, evidence coverage ≥0.5, and known in-window ratio ≥0.6; otherwise medium. Missing/unparseable post time is unknown, never guessed. Every failed gate emits a stable reason code. Empty input is low confidence.

## Import and market contracts

- Xiaohongshu import accepts JSON arrays, per-sector JSON maps, or JSONL. Valid sectors are the configured four. URLs must be HTTPS and Xiaohongshu-hosted. Zero valid records yields unavailable. Invalid individual records are rejected explicitly, not silently stripped.
- Source mode `imported` is added to internal/schema enums and history. Caveat precedence is simulated > imported > live. Public site checks continue to reject Xiaohongshu falsely labeled live.
- Market snapshots validate configured sectors, symbol/name, provider label, timezone-aware as-of/import timestamps, and any subset of 1d/5d/20d window returns. Missing or invalid snapshots degrade to unavailable and never break dashboard construction.

## Schema, compatibility, failure, and rollback

- Schema v3 requires top-level `market_context`; each sector has `sample_quality` object or null; methodology echoes confidence model version; source/history modes accept imported.
- v2 history loads additively and exports null quality. New UI renders v2 with a visible legacy notice; unknown payload versions render an error.
- Collection/import failure does not overwrite last-known-good history. Market failure only adds an unavailable context and warning.
- Existing privacy/secret scanning remains and banned identity keys expand.
- Rollback is an ordinary code/data ref rollback; workflows are unchanged.

## Acceptance criteria

- Xiaohongshu phrases above yield deterministic evidence; `抄底失败` is not buy/greed.
- Pre-existing Guba/scoring numeric tests pass and `compute_sector_index` numerics are unchanged.
- A 95-record title-only sample is objectively low-confidence with title-depth/time reasons.
- Adding/removing a market snapshot leaves sector index values byte-identical.
- Sanitized XHS import round-trips; author/cookie/token-like inputs are rejected and never exported.
- Existing v2 history builds a valid v3 payload; site checks retain the public XHS-live ban.
- v3 UI shows four blocks; v2 shows a legacy notice; JS syntax and site smoke checks pass.
- `interpret_index(9.4)` contains no bottom/predictive/trading language.
- Full repository quality gates pass and Claude/Fable 5 gives an approval-class final verdict.
