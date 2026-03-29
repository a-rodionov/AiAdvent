## REMOVED Requirements

### Requirement: Session propagates BillingEvent cost to usage statistics
**Reason**: `BillingEvent` is removed from the event stream. Billing calculation is now performed by `LlmStatsDecorator` using `ModelBilling.estimate()` on `CompletionDoneEvent.tokens_usage`. Session no longer inspects or handles `BillingEvent`.
**Migration**: Remove all `BillingEvent` handling code from `Session.acompletion`. The `LlmStatsDecorator` wrapping Session's `ILlmPort` handles cost computation and stats accumulation transparently.

### Requirement: SummaryStrategy propagates BillingEvent cost through _emit_token_usage
**Reason**: `BillingEvent` handling and `_emit_token_usage` are removed from `SummaryStrategy`. The strategy's `_llm` is now a `LlmStatsDecorator` that intercepts `CompletionDoneEvent` and handles stats accumulation, including optional billing via `ModelBilling.estimate()`.
**Migration**: Remove all `BillingEvent` handling and `_emit_token_usage` calls from `SummaryStrategy._apply_strategy`. The decorator handles this transparently.
