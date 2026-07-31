You are Claude Fable 5, acting as the architecture lead for the deployed Mom Index system. Work read-only. Do not modify files.

Read these files completely:
- `AGENTS.md`
- `.ai-orchestrator/agent-rules.md`
- `.ai-orchestrator/charter.md`
- `.ai-orchestrator/roles/claude-architect.md`
- `.ai-orchestrator/runs/20260731T165036Z-improve-live-mom-index/00-intake/request.en.md`
- `mom_index/collectors/guba.py`
- `mom_index/analysis/classifier.py`
- `mom_index/analysis/scoring.py`
- `mom_index/export.py`
- `mom_index/storage.py`
- `mom_index/validation.py`
- `schema/dashboard.schema.json`
- `frontend/index.html`
- `frontend/assets/app.js`
- `scripts/check_site.py`
- `tests/test_classifier.py`
- `tests/test_export.py`
- `tests/test_degraded.py`
- `README.md`

The current public system has one live unauthenticated source (Eastmoney Guba), about 294 posts in the latest run, low confidence for all four sectors, schema v3, deterministic formula 1.1, LKG storage, CI/Pages, and about 198 passing tests. Xiaohongshu and market context are currently unavailable. No new account, cookie, secret, paid API, login, or fabricated data is allowed in this wave.

Choose the smallest coherent implementation wave with the best trust/reliability return from these candidates:

A. A privacy-safe deterministic classifier evaluation corpus plus measurable precision/recall/regression CI gates.
B. Per-sector collection-quality diagnostics (requested/parsed/deduplicated/classifiable counts, failure reasons, source health) carried through export/schema and shown honestly in the dashboard.
C. User-facing confidence explanations that say exactly why confidence is low and what evidence is missing.

You may combine candidates only when the combined boundary remains small enough for one implementation task and the pieces form a necessary end-to-end slice. Prefer additive, backwards-compatible schema changes. Do not change formula 1.1, lower confidence thresholds, add providers, or redesign the site.

Return a concise build-ready contract containing exactly:
1. Selected wave and why it outranks the alternatives.
2. Current defects/gaps with exact file references.
3. File-by-file changes and interfaces, including field names/types/semantics if schema changes.
4. Invariants for privacy, degraded/LKG behavior, backward compatibility, and rollback.
5. Acceptance criteria and exact verification commands.
6. One implementation task manifest: objective, write scope, forbidden changes, deliverables, and dependencies.
7. Deferred follow-ups.

End with exactly one line: `DESIGN_READY`, `DESIGN_READY_WITH_QUESTIONS`, or `DESIGN_NOT_READY`.
