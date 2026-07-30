# Codex Design Adjudication

Accepted revision: `D-001@1`  
Architect response: Claude/Fable 5 R1  
Date: 2026-07-30

The architecture is build-ready. Claude's questions do not require new user authority because each has a reversible, low-risk default aligned with the user's request to deploy and optimize the existing project.

## Decisions

- **D1 — historical simulated records:** accept the default. Remove them from the public payload and retain only clearly labeled fixtures for tests. A short initial live history is more truthful than a visually fuller invented chart.
- **D2 — refresh cadence:** accept every six hours plus manual dispatch. This is sufficient for a sentiment dashboard and keeps public-source load low.
- **D3 — Xiaohongshu automation:** keep all login/API-key paths local-only and disabled by default. The public build reports Xiaohongshu as unavailable and never merges its sample posts into a live index.
- **D4 — release action:** Codex will use the already authenticated `xmkinc` GitHub account to create the pull request, merge only after checks and final review, enable GitHub Pages, trigger deployment, and verify the public URL. This external change is directly within the user's explicit deployment request and limited to the new fork.

## Clarifications binding implementation

- `data/dashboard_data.json` on the integration branch may begin with an honest degraded/empty seed. Live results belong to the `data` branch and must never be hand-edited to look current.
- A collection attempt that produces zero valid posts is not a live success. It must preserve the last successful index data, record an unavailable/degraded source status, and surface a warning.
- The generated public artifact contains summaries and source links only; it excludes author identity, cookies, credentials, and raw collected records.
- Any design-contract change discovered during implementation requires an ADR or a new design revision before integration.
