## Why

`BillingEvent` was added to ILlmPort interface. From now it's the responsibility of adapter to provide billing information. So users of ILlmPort don't have to duplicate logic of evaluation tokens cost based on token usage themselves.

## What Changes

- `Session.acompletion` will handle `BillingEvent` from the LLM port event stream.
- When a `BillingEvent` is received, its pre-computed cost fields (`provider`, `model`, `base_input_tokens_cost`, `output_tokens_cost`, `total_cost`) will be used to update session statistics directly instead of being calculated from `ModelPricing.estimate()`.
- `ModelPricing` removed from `Session` because not used in `Session` any more.
- `update_statistics` will be modified to accept pre-computed cost values directly and does not evalute cost itself anymore.
- `SummaryStrategy._apply_strategy` will handle `BillingEvent` from the LLM port event stream. When a `BillingEvent` is received, its pre-computed cost fields will be used for passing to function `_emit_token_usage`, `prompt_tokens` and `completion_tokens` will be 0 in this case.
- Signature of `MessageContextStrategy._emit_token_usage` changes to accept `base_input_tokens_cost`, `output_tokens_cost`, `total_cost`.
- Signature of `TokenUsageHandler` changes according to changes of `MessageContextStrategy._emit_token_usage`.
- Signature of `Session._handle_token_usage` changes according to changes of `MessageContextStrategy._emit_token_usage`.

## Capabilities

### New Capabilities

- `adapter-billing-propagation`: Session consumes `BillingEvent` from the LLM port stream and uses its cost figures to populate `UsageStatistics.tokens_cost`, bypassing local estimation when the adapter supplies exact billing data.
- `adapter-billing-propagation`: MessageContextStrategy consumes `BillingEvent` from the LLM port stream and uses its cost figures for calling \_emit_token_usage.

### Modified Capabilities

- `session`: `Session.acompletion` requirement changes — it must now handle the optional `BillingEvent` in the event stream and update statistics from it. The `model_pricing` dependency is removed.
- `session`: `Session._handle_token_usage` changes signature to accept already evaluated tokens cost as input parameters.
- Signature of `MessageContextStrategy._emit_token_usage` changes to accept `base_input_tokens_cost`, `output_tokens_cost`, `total_cost`.
- Signature of `TokenUsageHandler` changes according to changes of `MessageContextStrategy._emit_token_usage`.
- Signature of `Session._handle_token_usage` changes according to changes of `MessageContextStrategy._emit_token_usage`.
- Signature of `Session.update_statistics` changes according to changes of `MessageContextStrategy._emit_token_usage`.
- `Session.update_statistics` does not evalute cost itself anymore.

## Impact

- `app/domain/entities/session.py` — `Session.acompletion` loop, `_handle_token_usage`, constructor signature
- `app/domain/entities/context_strategy.py` — `SummaryStrategy._apply_strategy`, `_emit_token_usage` sigature, `TokenUsageHandler` sigature
- `app/domain/interfaces/llm_port.py` — `BillingEvent` import added to session and context_strategy consumers (no interface changes)
- `app/domain/value_objects/pricing.py` — `update_statistics` to accept direct cost values
- Tests for `Session.acompletion` will need scenarios covering the `BillingEvent`-present and `BillingEvent`-absent paths
- Tests for `SummaryStrategy._apply_strategy` will need scenarios covering the `BillingEvent`-present and `BillingEvent`-absent paths
