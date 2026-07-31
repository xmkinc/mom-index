# English Engineering Brief — Improve the Live Mom Index System

## Mission

Act as the senior architecture lead for the already deployed Mom Index repository. Inspect the current `origin/master` implementation and design the highest-value next improvement wave that Codex can implement immediately. The result must be an executable architecture contract, not a brainstorming list.

The user explicitly asked us to let Claude/Fable 5 assess how to improve the system and then start construction. Codex will adjudicate your contract, implement the accepted bounded wave in isolated Git worktrees, run all quality gates, and return the integrated result to Claude/Fable 5 for final design review. This run prepares a release candidate only; it must not merge or deploy.

## Product context

- The public site is already deployed through GitHub Pages at `https://xmkinc.github.io/mom-index/`.
- It is a static, auditable retail-sentiment dashboard for four sectors: Nasdaq, gold, CPO/optical communications, and semiconductors.
- The classifier and formula are deterministic. Formula version `1.1` must not be represented as a market forecast, causal signal, or validated trading strategy.
- The current public payload uses schema v3 and exposes source health, freshness, warnings, methodology, latest values, history, and representative public titles/links.
- The public scheduled path currently has one usable source: unauthenticated public Eastmoney Guba pages. The latest observed live run collected roughly 294 posts in total, leaving all four sector confidence labels low.
- Xiaohongshu is an explicit local-only boundary and is unavailable in the public workflow. Market context is also unavailable in the latest public payload. Neither absence may be hidden or filled with fabricated data.
- Data refresh uses a separate `data` branch with last-known-good behavior. Collection failures must preserve the last valid reading while truthfully marking the current source unavailable/stale/degraded.
- The repository currently has approximately 198 passing tests and existing CI, scheduled refresh, Pages deployment, site-build checks, JSON Schema validation, and operations documentation.

## Hard constraints

1. The immediate implementation wave must require no new user account, cookie, login session, paid API, secret, or provider contract.
2. Do not fabricate posts, prices, source availability, confidence, history, or backtest conclusions. Simulated data may exist only in explicit test/demo paths and must remain labeled simulated.
3. Public automation may use only compliant unauthenticated public endpoints. Do not add browser-profile scraping, CAPTCHA bypass, fingerprint evasion, credential capture, or private-person data.
4. Preserve privacy: no author identity, follower profile, cookies, credentials, raw private logs, or bulk raw-post publication.
5. Keep collection, classification, scoring, storage/export, and presentation boundaries explicit. Prefer backwards-compatible schema evolution; if a schema change is necessary, specify migration, compatibility, rollback, and validation.
6. Do not change formula `1.1` merely to make the number look better. Any proposed formula change must be deferred unless supported by a defined evaluation corpus, measurable evidence, versioning, and a migration plan.
7. Do not solve low confidence by silently lowering thresholds. Confidence must remain an honest quality signal.
8. Preserve static GitHub Pages deployment, deterministic builds, least-privilege workflows, LKG behavior, and operation during partial source failure.
9. Avoid cosmetic churn. Prioritize reliability, data quality, explainability, observability, and maintainability.

## Architecture questions to answer

Ground every observation in repository files and answer, in priority order:

1. What are the most important failure modes or trust gaps in the current live system?
2. What is the smallest coherent improvement wave we can safely build now without credentials, and why does it outrank alternatives?
3. How should we improve sample-quality diagnostics and user-facing confidence explanations without pretending that a larger sample exists?
4. How should we make collection/source health, partial-sector failure, deduplication, freshness, and last-known-good decisions more observable and testable?
5. Would a deterministic evaluation/calibration corpus materially reduce regression risk for the keyword classifier? If so, define its format, privacy rules, metrics, thresholds, and CI behavior without embedding real user identities.
6. Which improvements should wait for a compliant data-provider API or explicit user credentials? Define clean provider interfaces and decision criteria, but do not require those providers in this wave.
7. What frontend changes would help a non-technical reader understand why confidence is low, what data is missing, and what the number can and cannot mean?

## Required output

Provide a build-ready architecture contract with:

- current-state findings with exact file references;
- a prioritized decision: `must implement now`, `later with provider/credentials`, and explicit non-goals;
- proposed module boundaries, public interfaces, data flow, invariants, and dependency direction;
- concrete file-level changes, including any schema fields and their compatibility rules;
- security, privacy, failure, partial-success, migration, and rollback behavior;
- measurable acceptance criteria and exact executable verification commands;
- a dependency-ordered task plan with non-overlapping write scopes for Codex, Kimi, and/or WorkBuddy/GLM-5.2, using only workers that add real value;
- risks, alternatives considered, and why the selected immediate wave is the best return on complexity.

Keep the immediate wave bounded enough to implement and thoroughly verify in this run. If no user decision is truly required, return `DESIGN_READY`; do not manufacture questions merely to delay implementation.
