# Design Decisions

## D-001@1 — Explain quality before expanding sources

Accepted Claude/Fable 5's proposal to repair the backend/frontend reason-code mismatch and expose deterministic quality gates as the immediate implementation wave.

Rationale:

- It fixes a verified live communication defect.
- It requires no credentials, providers, new dependencies, or network access.
- It improves trust without changing the index, classifier, or confidence thresholds.
- It provides a bounded end-to-end slice with strong compatibility and regression tests.

## Worker exception

The repository charter normally assigns Claude/Fable 5 to architecture and final review. The user explicitly requested that Claude directly implement this wave. Therefore a fresh Claude Code/Fable 5 session will implement T-001 in an isolated worktree, while Codex retains scope adjudication, integration, executable verification, and user communication. A separate fresh Claude/Fable 5 session will perform final read-only review.
