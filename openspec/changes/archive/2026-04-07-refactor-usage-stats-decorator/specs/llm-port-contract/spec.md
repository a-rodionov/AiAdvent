## MODIFIED Requirements

### Requirement: ILlmPort interface is documented with purpose and contract

`ILlmPort` SHALL be a `typing.Protocol` (not an ABC) defining the contract for LLM completion providers. The domain layer depends only on this interface, never on concrete SDK types. Implementors satisfy the protocol through structural subtyping — they do not need to inherit from `ILlmPort`. The protocol defines a single method: `acompletion`.

#### Scenario: Class is a Protocol
- **WHEN** a developer inspects `ILlmPort` in `app/domain/interfaces/llm_port.py`
- **THEN** it inherits from `typing.Protocol`, not `abc.ABC`

#### Scenario: Structural subtyping works
- **WHEN** a class implements `acompletion` with a matching signature without inheriting from `ILlmPort`
- **THEN** mypy accepts it wherever `ILlmPort` is expected

### Requirement: Streaming event ordering is a normative contract

The `acompletion` async generator SHALL guarantee the following event ordering: zero or more `TextChunkEvent` events, followed by exactly one `CompletionDoneEvent` as the terminal event. No events SHALL be emitted after `CompletionDoneEvent`.

#### Scenario: Adapter emits events in correct order
- **WHEN** a conforming adapter yields events from `acompletion`
- **THEN** all `TextChunkEvent` items appear before `CompletionDoneEvent`, and `CompletionDoneEvent` is the last item yielded

#### Scenario: Non-streaming path still emits CompletionDoneEvent
- **WHEN** `is_stream_prefered` is `False` and the adapter uses a non-streaming API call
- **THEN** the generator still yields exactly one `CompletionDoneEvent` as its final (and potentially only) event

## REMOVED Requirements

### Requirement: CompletionEvent subclasses are documented — BillingEvent
**Reason**: `BillingEvent` is removed from the event stream contract. Billing calculation is now handled by `LlmStatsDecorator` via `ModelBilling.estimate()`, not by adapter-emitted events.
**Migration**: Remove all `BillingEvent` handling code from consumers. Use `LlmStatsDecorator` with `ModelBilling` to compute costs from `CompletionDoneEvent.tokens_usage`.
