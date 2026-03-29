## Context

`ModelBilling.estimate()` currently returns a `PricingResult` NamedTuple (`base_input_tokens_cost`, `output_tokens_cost`, `total_cost`). Session cost accumulation uses `TokensCost` (`prompt_tokens`, `completion_tokens`, `total_tokens`). Both types represent the same three-component cost breakdown with different field names, requiring implicit mapping between them whenever estimate results are used.

## Goals / Non-Goals

**Goals:**
- Remove `PricingResult` and make `ModelBilling.estimate()` return `TokensCost`
- Align field names across the billing and statistics subsystems
- Remove the `TestPricingResult` test class; keep and update estimate assertions

**Non-Goals:**
- Changing `TokensCost` field semantics or validation rules
- Modifying any file that already uses `TokensCost` (`llm_stats_decorator.py`, `usage_stats.py`, `ws_protocol.py`)
- Renaming `ModelBilling`, `ModelCostDTO`, or altering billing calculation logic

## Decisions

**Return `TokensCost` directly from `estimate()`**

`TokensCost` is a Pydantic `BaseModel` already used everywhere costs are consumed. Returning it from `estimate()` eliminates the conversion step and unifies the vocabulary. A NamedTuple with different field names was the wrong abstraction — it existed before `TokensCost` was introduced as the canonical cost type.

Field mapping:
| `PricingResult` field     | `TokensCost` field    |
|---------------------------|-----------------------|
| `base_input_tokens_cost`  | `prompt_tokens`       |
| `output_tokens_cost`      | `completion_tokens`   |
| `total_cost`              | `total_tokens`        |

**No intermediate adapter or deprecation shim**

`PricingResult` is only constructed in one place (`ModelBilling.estimate()`) and consumed only in tests. A deprecation path adds complexity for zero benefit — a direct replacement is safe and cleaner.

## Risks / Trade-offs

- [Breaking change in `model_billing.py` public API] → Acceptable: `PricingResult` is only used within the billing module and its own tests. No other production code references it.
- [`TokensCost.total_tokens` field name is ambiguous] → Pre-existing naming; out of scope for this change. The mapping (`total_cost` → `total_tokens`) is semantically correct even if the name is imprecise.

## Migration Plan

1. Update `model_billing.py`: remove `PricingResult`, change `estimate()` return type to `TokensCost`, construct `TokensCost` in the return statement.
2. Update `test_pricing.py`: remove `TestPricingResult` class, update `TestModelBilling.test_estimate_*` assertions to use `TokensCost` field names.
3. Run `pytest` and `mypy` to confirm no regressions.
