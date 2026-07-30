# Project Agent Charter

This repository uses Codex as the single user-facing engineering conductor, Claude/Fable 5 for architecture and final design review, and Codex/Kimi/WorkBuddy GLM-5.2 for isolated implementation.

Project-specific setup, verification, protected paths, deployment rules, and architectural constraints should be added below by Codex before the first production run.

## Setup

- Runtime target: Python 3.11+ for data generation and a static browser for the dashboard.
- Install only pinned, documented Python dependencies; never require local cookies or interactive logins for the public deployment path.
- The production site is a static GitHub Pages artifact built from repository files and generated public data.

## Verification

- Python unit/integration tests: `python -m pytest`.
- Python syntax/import smoke check: `python -m compileall analyzer collectors pipeline.py sync_data.py` (adjust paths when files are reorganized).
- Static-site smoke checks must validate JSON schema, relative asset/data paths, truthful source/provenance labels, and a usable stale/degraded-data state.
- The GitHub Actions workflow must be YAML-parseable and use least-privilege permissions.

## Protected paths

- `.github/workflows/**`
- production deployment configuration
- secrets and credential files

Any worker changing a protected path must have that exact path in its task manifest. Public automation must not embed credentials, cookies, private logs, or scraped personal data.

## Architectural constraints

- Never manufacture or silently label simulated data as live. Every metric must expose source, collection time, freshness, and degraded/simulated status.
- Public scheduled collection must use only unauthenticated public endpoints. Login-dependent Xiaohongshu collection remains an explicit local-only optional path unless a compliant public integration is designed later.
- Preserve a last-known-good dataset when a source temporarily fails, while clearly reporting staleness and failure state.
- Keep the scoring formula deterministic, documented, testable, and separated from collection and presentation.
- The dashboard must remain usable when JavaScript dependencies, a single data source, or a scheduled collection is unavailable.

## Release policy

- No direct writes to the default branch (`master`).
- All required checks must pass.
- Integrate through an `ai/<run>/integration` branch, open a pull request, and merge only after executable checks and Claude/Fable design review pass.
- Enable GitHub Pages through GitHub Actions only after the deployment workflow is merged.
