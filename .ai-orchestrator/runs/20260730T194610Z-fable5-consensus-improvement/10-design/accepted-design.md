# D-002@1 — Consensus improvement revision

## Must fix now

Scope compound overrides by platform. `抄底失败` must remain a sell/panic override for `platform="xiaohongshu"`, while the same Guba input must preserve the legacy ordinary-keyword behavior. The change must be deterministic and data-driven, not a hard-coded conditional in scoring. Formula 1.1 and `compute_sector_index` remain untouched.

Acceptance criteria:

1. Xiaohongshu `抄底失败被套了` remains sell intent with non-positive sentiment and its inner `抄底` buy/greed hit is suppressed.
2. Guba `抄底失败` receives no platform extension or compound override and preserves the baseline ordinary `抄底` behavior.
3. Compound configuration is explicitly keyed by platform; unknown platforms receive no overrides.
4. Focused classifier/scoring tests and the full suite pass.

## Accepted release behavior

- Public scheduled builds intentionally show unavailable market context because no compliant public adapter was authorized. Do not add a network provider or workflow change.
- WorkBuddy's Bash denial and Codex takeover are preserved as process evidence; no product change is needed.

## Verification improvement

Perform explicit local visual QA for desktop and mobile widths on schema v3. Retain the existing mocked v2/unknown-version runtime smoke and static site checks. Record screenshots or inspected evidence without committing generated site artifacts.

## Non-goals

- No scoring formula, schema, import, market, workflow, credential, public provider, or deployment change.
