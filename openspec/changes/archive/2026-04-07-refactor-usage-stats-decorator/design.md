## Context

The current codebase uses a callback-based pattern for tracking token usage statistics. `Session` manually parses `BillingEvent` and `CompletionDoneEvent` in its `acompletion()` method, calling `_handle_token_usage()` to accumulate stats. `MessageContextStrategy` mirrors this with `OnTokenUsage`/`_emit_token_usage` callbacks that bubble usage up to `Session`. This scatters billing logic across two layers and couples `Session` to event-parsing details that are not part of its core responsibility.

The architecture follows hexagonal principles with four layers: domain (pure Python), use_cases (orchestration), adapters (concrete implementations), and infrastructure (wiring). All new types must respect these boundaries.

## Goals / Non-Goals

**Goals:**
- Centralize token usage and billing accumulation into a single decorator (`LlmStatsDecorator`) that wraps `ILlmPort`.
- Introduce `SessionUsageStats` as a two-level accumulator (per-invocation + lifecycle) owned by `Session`.
- Enable structural subtyping for `ILlmPort` and `UsageStats` via Protocol.
- Decouple `ModelBilling` (renamed from `ModelPricing`) from `ModelPricingDTO`.
- Introduce factory patterns for `ILlmPort` and `ModelBilling` creation.
- Remove all callback-based stats tracking (`OnTokenUsage`, `_emit_token_usage`, `BillingEvent`).

**Non-Goals:**
- Changing the external REST/WebSocket API contract.
- Modifying `LlmAdapter` internals or the any-llm SDK integration.
- Adding new billing providers or pricing models.
- Changing persistence format for `SessionDto`.

## Decisions

### Decision 1: LlmStatsDecorator in the domain layer (not adapters)

`LlmStatsDecorator` is placed in the domain layer because it orchestrates domain concepts (usage stats, billing estimation) and implements the `ILlmPort` Protocol. It contains no I/O — it merely wraps another `ILlmPort` and intercepts events in the async generator stream.

**Alternative considered**: Placing it in adapters. Rejected because it depends only on domain types and has no infrastructure dependencies.

### Decision 2: Protocol over ABC for ILlmPort and UsageStats

Using `typing.Protocol` enables structural subtyping. `LlmStatsDecorator` satisfies `ILlmPort` without inheriting from it. `SessionUsageStats` satisfies the `UsageStats` protocol without inheritance, which is the primary motivation — it allows `SessionUsageStats` to be passed anywhere a `UsageStats` is expected.

**Alternative considered**: Keep ABC and use inheritance. Rejected because it forces `SessionUsageStats` to inherit from `UsageStats` and override `__init__`, which is awkward for a class with different construction semantics.

### Decision 3: Session owns SessionUsageStats, shares references to decorators

`Session` creates a single `SessionUsageStats` instance and passes the same reference to both `LlmStatsDecorator` instances (one for Session's own completions, one for the strategy's). Both decorators accumulate into the same object. This ensures a single source of truth for stats.

```
Session
  └── SessionUsageStats (single instance, owned by Session)
        │
        ├──► LlmStatsDecorator (wraps Session's ILlmPort)
        │      └── calls SessionUsageStats.add_stats()
        │
        └──► LlmStatsDecorator (wraps Strategy's ILlmPort)
               └── calls SessionUsageStats.add_stats()
```

**Alternative considered**: Each decorator owns its own `UsageStats` and Session merges them. Rejected because it complicates aggregation and breaks the single-source-of-truth principle.

### Decision 4: ModelBilling constructed from raw parameters, factory handles DTO mapping

`ModelBilling` takes `tokens_per_price: int`, `base_input_tokens: float`, `output_tokens: float` — no dependency on `ModelPricingDTO`. The factory adapter reads the pricing file, caches DTOs, and extracts raw parameters when creating `ModelBilling`.

**Alternative considered**: Keep `ModelBilling` accepting DTOs. Rejected because it violates the principle that domain objects should not depend on DTO types.

### Decision 5: ILlmPortFactory caches adapters per (session_id, provider)

The factory adapter maintains a nested dict `{session_id: {provider: LlmAdapter}}`. If an adapter already exists for the requested key, it's returned; otherwise a new one is created. This prevents redundant SDK client instantiation while isolating adapters per session.

**Alternative considered**: Global cache by provider only (no session_id dimension). Would work for the current `LlmAdapter` which is stateless per-request, but the session-scoped cache is safer for future adapters that might carry per-session state.

### Decision 6: Session constructor takes factory build parameters instead of pre-built strategy

Session's constructor accepts the raw parameters needed to call `MessageContextStrategyFactory.build()` and builds the strategy internally. This is necessary because Session needs to wrap the strategy's `ILlmPort` with a `LlmStatsDecorator` before passing it to the factory — something that can't happen if the strategy is pre-built externally.

**Alternative considered**: Keep pre-built strategy and rewire after construction. Rejected because it would require exposing strategy internals and would be error-prone (the strategy might already have made LLM calls during `_apply_strategy` with the unwrapped port).

### Decision 7: Remove BillingEvent entirely

Currently `LlmAdapter` does not emit `BillingEvent` — only `Session` and `SummaryStrategy` have dead code to handle it. Billing calculation moves entirely to `LlmStatsDecorator` via `ModelBilling.estimate()`, making `BillingEvent` obsolete.

**Alternative considered**: Keep `BillingEvent` for adapters that compute cost natively. Rejected because no adapter currently uses it, and `ModelBilling` provides a cleaner, centralized approach.

## Risks / Trade-offs

**[Risk] Session constructor becomes more complex with factory parameters** → Mitigated by clear parameter grouping and the fact that use cases handle the orchestration of creating factories and passing them in.

**[Risk] Two LlmStatsDecorators sharing one SessionUsageStats could have concurrency issues** → Mitigated by the fact that Session processes completions sequentially (one `acompletion` at a time). Strategy summarization happens within the same async flow.

**[Risk] Removing BillingEvent is a breaking change for any external adapter emitting it** → Mitigated by the fact that no adapter currently emits `BillingEvent` and this is an internal library.

**[Trade-off] Protocol-based UsageStats loses IDE autocomplete for concrete methods** → Accepted because the Protocol defines the same method signatures, and the concrete `UsageStats` class still exists for direct usage.

**[Trade-off] Factory pattern adds indirection** → Accepted because it decouples Session from adapter construction and enables proper decorator wiring.
