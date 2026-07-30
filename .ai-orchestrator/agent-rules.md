# Multi-Agent Repository Rules

## Shared state

Git commits and files under `.ai-orchestrator/` are the authoritative shared state. Chat history and uncommitted files are not handoffs.

## Authority

1. Claude/Fable 5 owns accepted architecture and final design review.
2. Codex owns task decomposition, worker selection, integration, executable quality gates, and the user report.
3. Codex, Kimi, and WorkBuddy/GLM-5.2 implement bounded tasks.
4. Only Codex integrates worker commits. No worker merges or writes directly to `main`.

## Required behavior

- Read the assigned role, accepted design, and task manifest before editing.
- Work only on the assigned branch/worktree.
- Modify only task `write_scope` paths.
- Stop and report when a required change is outside scope.
- Never discard or rewrite another agent's work.
- Run required verification, create an atomic commit, and write a handoff.
- Never commit secrets, credentials, tokens, cookies, `.env` files, or raw private logs.
- Never force-push or bypass repository protections.

## Handoff minimum

Record task ID, agent/model, branch, base SHA, commit SHA, changed files, verification commands/results, known risks, and out-of-scope findings.
