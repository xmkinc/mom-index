# T-007 Codex handoff

- Task: `T-007` — Align imported Xiaohongshu URL export allowlist
- Agent: Codex
- Spec: `D-001@1`
- Branch: `ai/20260730T182929Z-complete-crash-aware-index/codex/T-007`
- Immutable base: `0d4129a5339c22f4f00e8c2d4a499869eb559463`
- Implementation commit: `916a52b9b49fe9a6bb51313459748da382d2bc88`

## Delivery

- Added exact `xiaohongshu.com` bare-host support to the existing public post URL allowlist so links accepted by the sanitized import schema are not silently dropped.
- Hardened public URL export to reject user information, passwords, explicit ports, whitespace/control characters, deceptive subdomains, non-HTTPS schemes, and malformed ports.
- Kept the existing exact allowed hosts for Eastmoney and Xiaohongshu; no wildcard or suffix matching was introduced.

## Changed files

- `mom_index/export.py`
- `tests/test_export.py`

## Verification

- `python -m pytest -q tests/test_export.py tests/test_xhs_import.py` — 85 passed.
- `git diff --check` — passed.
- Tests cover bare and `www` Xiaohongshu URLs plus HTTP, deceptive domains, embedded credentials, explicit ports, whitespace, and JavaScript schemes.

No scoring, workflow, collector, schema, deployment, or default-branch change was made.
