## Why

`PricingResult` (a `NamedTuple`) and `TokensCost` (a Pydantic `BaseModel`) both represent a breakdown of LLM call costs into prompt, completion, and total components, but with different field names. Having two separate types for the same concept creates redundancy: callers of `ModelBilling.estimate()` must convert `PricingResult` into `TokensCost` when accumulating session statistics, and the codebase maintains two parallel vocabularies for the same idea.

## What Changes

- **BREAKING** Remove `PricingResult` from `model_billing.py`
- **BREAKING** Change `ModelBilling.estimate()` return type from `PricingResult` to `TokensCost`
- Update `ModelBilling.estimate()` implementation to construct and return a `TokensCost` instance using field names: `prompt_tokens` (was `base_input_tokens_cost`), `completion_tokens` (was `output_tokens_cost`), `total_tokens` (was `total_cost`)
- Remove `test_pricing.py::TestPricingResult` and update `TestModelBilling.test_estimate_*` assertions to use `TokensCost` field names

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `model-pricing`: `ModelBilling.estimate()` now returns `TokensCost` instead of `PricingResult`; `PricingResult` requirement is removed

## Impact

- `server/application/domain/model/model_billing.py` — remove `PricingResult`, update `ModelBilling.estimate()` return type and body
- `tests/domain/value_objects/test_pricing.py` — remove `TestPricingResult` class, update estimate assertions
- No changes required in `llm_stats_decorator.py`, `usage_stats.py`, or `ws_protocol.py` — they already use `TokensCost` directly
