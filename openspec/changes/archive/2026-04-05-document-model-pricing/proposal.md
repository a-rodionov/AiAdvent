## Why

The pricing subsystem (`ModelPricingDTO`, `PricingResult`, `TokensCost`, `UsageStatistics`, `ModelPricing`) is used throughout the session layer for cost estimation and accumulation, yet has no written specification. Documenting it now completes the domain-layer spec coverage alongside `message-context-strategy` and `session`.

## What Changes

- Add a specification for `ModelPricingDTO` — the Pydantic DTO carrying per-model pricing configuration and its validation rules.
- Document `PricingResult` — the immutable NamedTuple returned by `ModelPricing.estimate()`.
- Document `TokensCost` — the Pydantic model tracking accumulated costs (prompt, completion, total) in currency units, used inside `UsageStatistics`.
- Document `UsageStatistics` — the compound model pairing token counts with optional cost data, keyed per provider/model in session statistics.
- Document `ModelPricing` — the pricing engine: construction, lookup, the cost-estimation formula, and error behaviour for unknown models.

## Capabilities

### New Capabilities

- `model-pricing`: Specification for the pricing engine and its supporting value objects — `ModelPricingDTO`, `PricingResult`, `TokensCost`, `UsageStatistics`, and `ModelPricing` — covering data contracts, validation rules, the estimation formula, and error cases.

### Modified Capabilities

## Impact

- No production code changes; documentation only.
- Affects: `app/domain/value_objects/pricing.py`, `tests/domain/value_objects/test_pricing.py`, `app/adapters/gateways/pricing_file_adapter.py` (consumer of `ModelPricingDTO`), `app/domain/entities/session.py` (consumer of `ModelPricing`, `TokensCost`, `UsageStatistics`).
