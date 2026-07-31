# Accepted defaults

- Imported Xiaohongshu and market snapshots remain local-only; no workflow changes.
- Primary market references use configured A-share ETF symbols; optional labeled secondary symbols are allowed by import data.
- Return windows are 1d, 5d, and 20d.
- Sample freshness window is 72 hours.
- Low-band text describes sparse novice evidence and explicitly disclaims bottom calls.
- Formula version 1.1 and all numeric weights remain unchanged.

## Execution amendment

- T-005 was explicitly reassigned to Codex as T-005R after the WorkBuddy background CLI refused Bash in non-interactive `acceptEdits` mode. No bypass or full-access permission was enabled.
- T-003 implementation was produced by WorkBuddy but left unverified and uncommitted for the same Bash restriction. T-003R assigns Codex to review, test, repair, and commit that bounded delivery; WorkBuddy's original handoff is preserved.
- T-007 closes the integration finding that the sanitized importer/schema accepted the bare Xiaohongshu host while public URL export retained only the `www` host.
