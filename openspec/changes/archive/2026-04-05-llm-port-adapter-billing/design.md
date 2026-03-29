## Context

`ILlmPort.acompletion` emits an optional `BillingEvent` before the terminal `CompletionDoneEvent`. Adapters that have access to provider-native billing APIs (e.g., Anthropic's `usage` response field) can populate exact cost figures there.

Currently, neither `Session` nor `SummaryStrategy` handle `BillingEvent`. Both pass raw token counts from `CompletionDoneEvent` to `ModelPricing.estimate()`, which re-derives costs from a static pricing table. This creates a split-brain situation: the adapter already knows the real cost, but the domain layer ignores it and computes its own estimate.

## Goals / Non-Goals

**Goals:**
- When a `BillingEvent` is present in the stream, use its pre-computed cost figures in `UsageStatistics` instead of calling `ModelPricing.estimate()`.
- Remove `ModelPricing` from `Session` — cost estimation is no longer the session's responsibility.
- Propagate the signature change through `_emit_token_usage` → `TokenUsageHandler` → `Session._handle_token_usage` → `update_statistics` so all cost values are passed in, never derived in the domain.

**Non-Goals:**
- Adding `BillingEvent` support to adapters that don't yet emit it (adapter implementation is out of scope).
- Changing how `UsageStatistics` or `TokensCost` are stored or serialised.
- Deprecating `ModelPricing` globally — it may still be used outside `Session` (e.g., pre-flight cost estimation).

## Decisions

### 1. Capture `BillingEvent` in the stream loop; pass costs down via a changed signature

Both `Session.acompletion` and `SummaryStrategy._apply_strategy` iterate the `ILlmPort` event stream. The simplest change is to set a local `billing_event: BillingEvent | None = None` variable in the loop, then — when `CompletionDoneEvent` arrives — decide which cost source to use.

**Alternative considered — a separate callback for billing:** Registering an `OnBillingEvent` handler analogous to `OnTokenUsage` was considered. Rejected because it adds indirection for no gain: both `CompletionDoneEvent` and `BillingEvent` arrive in the same loop and the correlation is trivial.

### 2. `_emit_token_usage` accepts pre-computed costs, not raw tokens

New signature:
```
_emit_token_usage(
    provider, model,
    prompt_tokens, completion_tokens,
    base_input_tokens_cost, output_tokens_cost, total_cost
)
```

When `BillingEvent` is present: pass its cost fields, and pass `prompt_tokens=0, completion_tokens=0` (token counts come from `CompletionDoneEvent` if callers need them — but `SummaryStrategy` only needs cost, not counts).

When `BillingEvent` is absent: pass `base_input_tokens_cost=0.0, output_tokens_cost=0.0, total_cost=0.0` — callers that still need cost estimation must handle this themselves, or cost is simply not recorded.

**Note on `SummaryStrategy`:** The strategy uses `_emit_token_usage` only to propagate cost upstream to `Session._handle_token_usage`. It does not accumulate statistics itself. So passing zeros for token counts when a `BillingEvent` is present is acceptable — the session-level accounting uses the cost fields, not the counts.

**Alternative considered — keep counts and costs separate:** Two handlers (one for counts, one for costs) would avoid null-like zero values. Rejected because it doubles the handler plumbing and the current domain model (UsageStatistics) already bundles both in one struct.

### 3. `update_statistics` accepts cost values directly; `model_pricing` parameter removed

New signature:
```
update_statistics(
    usage_statistics, provider, model,
    prompt_tokens, completion_tokens,
    base_input_tokens_cost, output_tokens_cost, total_cost
)
```

This is a pure data-accumulation function in the domain layer — no I/O, no pricing engine. Consistent with the rule that the domain layer must not own infrastructure state.

### 4. `ModelPricing` removed from `Session.__init__`

With `update_statistics` no longer calling `model_pricing.estimate()`, `Session` has no use for a `ModelPricing` instance. The constructor parameter, `create()` classmethod parameter, and `from_dto()` classmethod parameter all drop it.

Call sites (infrastructure / use-case layer) that currently inject `ModelPricing` into `Session` will need to be updated.

## Risks / Trade-offs

- **Zero costs when `BillingEvent` absent** → `tokens_cost` in `UsageStatistics` will have all-zero fields when no adapter supplies billing data, rather than an estimated value. This is a deliberate accuracy trade-off: an absent estimate is clearer than a potentially wrong estimate. → Mitigation: document this in `update_statistics` docstring; callers can detect zero-cost entries if needed.

- **Signature churn across the call chain** → Four signatures change in one sweep (`_emit_token_usage`, `TokenUsageHandler`, `_handle_token_usage`, `update_statistics`). → Mitigation: changes are confined to the domain layer; the test suite will catch any missed call site.

- **`SummaryStrategy` passing `prompt_tokens=0, completion_tokens=0`** → Token count accumulation in session statistics will be incomplete for summarisation turns that have a `BillingEvent`. → Mitigation: `CompletionDoneEvent` always carries `tokens_usage`; if token counts are needed they can be plumbed separately. Tracked as open question below.

## Migration Plan

1. Update `_emit_token_usage` and `TokenUsageHandler` type alias in `context_strategy.py`.
2. Update `SummaryStrategy._apply_strategy` to capture `BillingEvent` and pass cost fields.
3. Update `update_statistics` in `session.py` to accept direct cost values.
4. Update `Session._handle_token_usage` to match new `TokenUsageHandler` shape.
5. Update `Session.acompletion` to capture `BillingEvent` and pass cost fields.
6. Remove `model_pricing` from `Session.__init__`, `Session.create`, `Session.from_dto`.
7. Update all infrastructure/use-case call sites that construct `Session`.
8. Update unit tests: add `BillingEvent`-present and `BillingEvent`-absent paths for both `Session.acompletion` and `SummaryStrategy._apply_strategy`.

No migration of persisted data is required — `SessionDto` does not store pricing configuration.

Rollback: the change is self-contained in the domain layer. Reverting the four files is sufficient.

## Open Questions

- Should `_emit_token_usage` also carry `prompt_tokens` and `completion_tokens` from `CompletionDoneEvent` when a `BillingEvent` is present, so `UsageStatistics.tokens_usage` stays accurate for summarisation turns? Currently the proposal passes zeros. Confirm intent before implementing tasks.
