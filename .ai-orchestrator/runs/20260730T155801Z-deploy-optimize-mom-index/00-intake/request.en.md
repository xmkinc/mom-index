# English Engineering Brief

## User objective

Fork `mihang123/mom-index`, deploy a publicly accessible version under the user's GitHub account, and improve the project from that baseline. The deployment itself is part of the requested outcome, not merely a recommendation.

## Current repository state

- Default branch: `master`; baseline commit: `0c68a455b60a973c6e31ea7c8c335c868ba346f2`.
- Python collectors and a deterministic rule-based index calculator generate JSON data.
- The dashboard is a static `frontend/dashboard.html` page using Chart.js.
- Guba is the only reasonably live public source. Xiaohongshu data in the repository is simulated or requires an interactive login and therefore cannot be presented as live in unattended public automation.
- There are no dependency lock files, automated tests, CI, scheduled updates, or deployment workflow.

## Required outcomes

1. Publish a working GitHub Pages site from the fork `xmkinc/mom-index`, with a stable public URL and a repeatable deployment workflow.
2. Add an unattended scheduled refresh that uses only permitted unauthenticated public data sources. A source failure must preserve last-known-good data and visibly report stale/degraded status; it must never fabricate a successful live update.
3. Separate collection, scoring, public-data packaging, and presentation sufficiently to make the pipeline testable and maintainable.
4. Make the index schema self-describing: include collection/generation timestamps, source provenance, source mode (`live`, `simulated`, `unavailable`, or equivalent), freshness, and errors/warnings without exposing credentials, cookies, raw private data, or unnecessary post content.
5. Keep the scoring deterministic and documented. Fix correctness and robustness issues found in the original implementation and add tests around formulas, thresholds, malformed/empty data, and public export behavior.
6. Improve the static dashboard for mobile and desktop: clear current readings, trend/context, plain-language methodology, update time, source/freshness status, graceful loading/error/empty states, and accessible interaction. Do not present simulated Xiaohongshu data as live evidence.
7. Add minimal reproducible developer setup, CI checks, scheduled deployment, and operational documentation.
8. Preserve the original project's spirit and four initial sectors (Nasdaq, Gold, CPO, Semiconductor); avoid an unrelated wholesale product rewrite.

## Constraints

- Production hosting: GitHub Pages via GitHub Actions.
- Python 3.11+ for automation; static HTML/CSS/JavaScript in the browser. Avoid a server that GitHub Pages cannot run.
- Public automation must not depend on interactive sessions, credentials, paid APIs, or secrets unless explicitly optional and disabled by default.
- Apply least-privilege GitHub Actions permissions and do not commit generated secrets, cookies, `.env` files, or raw personal content.
- Use an integration branch and pull request; do not write directly to `master`.
- All executable checks and Claude/Fable final design review must pass before merge and deployment.

## Acceptance criteria

- A merged GitHub Actions Pages workflow produces a reachable `https://xmkinc.github.io/mom-index/` deployment.
- A scheduled/manual workflow can refresh public data, validate it, build the site artifact, and deploy it; failed collection is distinguishable from a current successful update.
- Unit/integration tests and static-site smoke checks pass locally and in CI.
- The page visibly states data source modes, last update, freshness/degraded status, and methodology limitations.
- Repository documentation contains exact local-run, test, deployment, and troubleshooting instructions.
- No simulated data is labeled or implied as live.
