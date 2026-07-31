# Fable 5 review basis and adapter incident

The prior Fable 5 final review at `.ai-orchestrator/runs/20260730T182929Z-complete-crash-aware-index/40-review/claude-review.md` returned `APPROVE_WITH_NOTES` and identified one concrete code tension: `COMPOUND_OVERRIDES` was global, so `抄底失败` could change Guba behavior despite the platform-invariance goal.

For this consensus run, the Fable 5 adapter was invoked three times for a narrower adjudication: one response disconnected mid-stream and two requests remained non-responsive for hours and were interrupted. No partial response was treated as a verdict. Codex therefore accepts the smallest correction directly supported by the previous Fable review and the already accepted design, preserves the other notes as explicit decisions, and will request a fresh Fable 5 final review after implementation.
