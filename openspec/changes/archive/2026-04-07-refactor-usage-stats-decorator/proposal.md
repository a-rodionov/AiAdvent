## Why

Token usage statistics tracking is currently scattered across `Session.acompletion()` and `MessageContextStrategy._emit_token_usage()` via a callback-based pattern (`OnTokenUsage`/`_emit_token_usage`). This couples billing logic tightly to both the session aggregate and the strategy layer, making the code harder to reason about and extend. Centralizing stats accumulation into a decorator that wraps `ILlmPort` will separate concerns: `Session` and strategies focus on conversation management, while the decorator transparently intercepts completion streams to track usage.

## What Changes

- **ILlmPort**: Change base class from `ABC` to `Protocol` to enable structural subtyping.
- **UsageStats**: Change to a `Protocol` so that `SessionUsageStats` can satisfy it structurally without inheritance.
- **New `SessionUsageStats`**: Domain value object with two `UsageStats` members (`_current_invocation` for per-request stats, `_lifecycle_total` for cumulative stats). Owned by `Session`.
- **Rename `ModelPricing` to `ModelBilling`**: Decouple from `ModelPricingDTO` — construct from raw parameters. Rename file `pricing.py` to `model_billing.py`.
- **New `ModelBillingFactory` port and adapter**: Factory port to create `ModelBilling` from `(provider, model)`. Adapter reads pricing file, caches DTOs in memory, returns `None` for unknown pairs.
- **New `LlmStatsDecorator`**: Domain-layer decorator wrapping `ILlmPort`. Intercepts `CompletionDoneEvent` to extract token usage, optionally estimate cost via `ModelBilling`, and call `SessionUsageStats.add_stats`. `TextChunkEvent` passes through unchanged.
- **Session refactoring**: Replace `_statistics`/`_request_statistics` with a single `SessionUsageStats`. Session creates two `LlmStatsDecorator` instances (one for its own completions, one for the strategy's), both sharing the same `SessionUsageStats` reference. Remove `_handle_token_usage`.
- **New `ILlmPortFactory` port and adapter**: Factory for creating/caching `LlmAdapter` instances per `(session_id, provider)`. Used in use cases and Session constructor.
- **Strategy cleanup**: Remove `OnTokenUsage`, `_emit_token_usage`, `TokenUsageHandler` from `MessageContextStrategy`. Strategy receives `LlmStatsDecorator` (satisfying `ILlmPort` Protocol) instead of raw `ILlmPort`.
- **Remove `BillingEvent`**: No longer needed — billing calculation moves into `LlmStatsDecorator` via `ModelBilling.estimate`.

## Capabilities

### New Capabilities
- `llm-stats-decorator`: Decorator wrapping `ILlmPort` that transparently intercepts completion streams to accumulate token usage and optional cost into `SessionUsageStats`.
- `session-usage-stats`: Two-level stats accumulator (per-invocation + lifecycle total) owned by `Session`, shared across decorators.
- `llm-port-factory`: Factory port and adapter for creating and caching `ILlmPort` instances per session and provider.
- `model-billing-factory`: Factory port and adapter for creating `ModelBilling` from provider/model using cached pricing data.

### Modified Capabilities
- `llm-port-contract`: `ILlmPort` base class changes from `ABC` to `Protocol`. `BillingEvent` is removed from the event stream contract.
- `usage-stats`: `UsageStats` becomes a `Protocol` instead of a concrete class to enable structural subtyping by `SessionUsageStats`.
- `session`: `Session` constructor changes to accept factories and `ModelBilling` instead of pre-built strategy. Stats tracking delegated to `LlmStatsDecorator`. `_handle_token_usage` removed.
- `message-context-strategy`: `OnTokenUsage`, `_emit_token_usage`, and `TokenUsageHandler` removed. Strategy receives `ILlmPort`-conformant object (which will be a `LlmStatsDecorator`).
- `model-pricing`: `ModelPricing` renamed to `ModelBilling`, decoupled from `ModelPricingDTO`, file renamed to `model_billing.py`.
- `adapter-billing-propagation`: Entire capability removed — billing propagation is replaced by `LlmStatsDecorator`.

## Impact

- **Domain layer**: `ILlmPort`, `UsageStats`, `Session`, `MessageContextStrategy`, `ModelPricing` — all modified. New files: `LlmStatsDecorator`, `SessionUsageStats`, factory ports.
- **Adapters**: `LlmAdapter` unchanged but no longer emits `BillingEvent`. `ModelPricingFileAdapter` refactored into `ModelBillingFactory` adapter. New `ILlmPortFactory` adapter.
- **Use cases**: `CreateSessionUseCase` and `GetSessionUseCase` updated to use factories and pass `ModelBilling` to `Session`.
- **Infrastructure**: `app_factory.py` updated to wire new factories.
- **Tests**: All tests touching `Session`, `MessageContextStrategy`, `UsageStats`, `ModelPricing`, and billing event handling will need updates.
- **No external API changes**: `SessionCompletionDoneEvent` and REST/WS contract remain the same.
