## Context

All pricing types live in `app/domain/value_objects/pricing.py` (pure domain layer, no I/O). They form a single cohesive subsystem:

- **`ModelPricingDTO`** — Pydantic input model for per-model rates loaded from config (e.g. JSON via `ModelPricingFileAdapter`). Validated at load time.
- **`PricingResult`** — transient NamedTuple output of `ModelPricing.estimate()`. Never persisted.
- **`TokensCost`** — Pydantic model that accumulates monetary cost over the lifetime of a session. Stored inside `SessionDto` via `UsageStatistics`.
- **`UsageStatistics`** — pairs a `TokensUsage` (token counts) with an optional `TokensCost`. Used as the value type in `Session.statistics` and `SessionCompletionDoneEvent.statistics`.
- **`ModelPricing`** — the runtime pricing engine. Built from a list of DTOs; exposes `estimate()` using the formula: `cost = token_count × rate / tokens_per_price`.

There is a notable module-level design detail: `UsageStatistics` references `TokensUsage` which lives in `completion.py`. To avoid a circular import, `TokensUsage` is imported at the bottom of `pricing.py` after the class bodies, and `UsageStatistics.model_rebuild()` is called explicitly.

The change is **documentation-only**: one `specs/model-pricing/spec.md` captures all contracts.

## Goals / Non-Goals

**Goals:**
- Produce `specs/model-pricing/spec.md` covering all five types with their validation rules, the estimation formula, and error cases.
- Every scenario maps to an existing test in `tests/domain/value_objects/test_pricing.py`.

**Non-Goals:**
- No production code changes.
- No changes to the `ModelPricingFileAdapter` or config format.
- No extension of the pricing formula (e.g., tiered pricing) — that is future scope.

## Decisions

### Decision 1 — one spec file for all five types
**Chosen:** `specs/model-pricing/spec.md` covers `ModelPricingDTO`, `PricingResult`, `TokensCost`, `UsageStatistics`, and `ModelPricing` together.

**Alternatives considered:**
- Separate spec per type — the types are tightly coupled (DTO feeds engine; engine returns `PricingResult`; `TokensCost` and `UsageStatistics` are consumed by the same session layer). Splitting inflates navigation cost with no benefit.

**Rationale:** All five types form one pricing subsystem. A reader understanding cost estimation needs all five in view.

### Decision 2 — document the formula verbatim in the spec
The cost formula (`cost = token_count × rate / tokens_per_price`) is non-obvious: it uses "price per N tokens" rather than "price per token" to match LLM provider conventions. The spec SHALL state the formula explicitly so future implementers don't accidentally invert the operands.

### Decision 3 — PricingResult vs TokensCost: document the intentional duality
`PricingResult` (NamedTuple, transient) and `TokensCost` (Pydantic, persistent) serve the same conceptual purpose but have different characteristics. The spec should note this distinction so the two types are not inadvertently merged.

## Risks / Trade-offs

- **Risk: `UsageStatistics` circular import is fragile** — if `pricing.py` is ever refactored, the bottom-of-module import of `TokensUsage` must be preserved or the circular dependency resolved properly. Documented as a known constraint.
- **Risk: `ModelPricing.estimate()` raises `KeyError` (not `ValueError`) for unknown models** — callers must catch `KeyError`. The spec documents this so callers know which exception to handle.
- **Trade-off: no tiered or volume pricing** — the current formula is linear. Any future change to the formula is a breaking change to `PricingResult` semantics and will need a spec update.

## Open Questions

- Should `ModelPricing.estimate()` raise `ValueError` instead of `KeyError` for consistency with the rest of the domain? Left as-is for now to match current behaviour; revisit if a new LLM gateway requires unified error handling.
