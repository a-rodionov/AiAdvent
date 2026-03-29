## ADDED Requirements

### Requirement: ILlmPort interface is documented with purpose and contract
`ILlmPort` SHALL have a class-level docstring that states: it is a hexagonal-architecture port defining the contract for LLM completion providers; the domain layer depends only on this interface, never on concrete SDK types; implementors must subclass it and override `acompletion`.

#### Scenario: Class docstring present
- **WHEN** a developer inspects `ILlmPort` in `app/domain/interfaces/llm_port.py`
- **THEN** a class-level docstring is visible that explains the port's role in hexagonal architecture and lists the single abstract method

### Requirement: acompletion method is documented with parameter and return semantics
`acompletion` SHALL have a docstring covering: each parameter's purpose (`full_messages`, `completion_config`, `is_stream_prefered`), the return type as an async generator of `CompletionEvent` subclasses, and the guaranteed event ordering contract.

#### Scenario: Method docstring covers all parameters
- **WHEN** a developer reads the `acompletion` docstring
- **THEN** they can identify the purpose of `full_messages` (conversation history in provider-native format), `completion_config` (provider/model/sampling settings), and `is_stream_prefered` (hint to adapter to use streaming API if available)

#### Scenario: Return contract is documented
- **WHEN** a developer reads the `acompletion` docstring
- **THEN** the docstring states that the generator MUST yield zero or more `TextChunkEvent` items, then optionally a `BillingEvent`, and MUST yield exactly one `CompletionDoneEvent` as the final event

### Requirement: CompletionEvent subclasses are documented
Each `CompletionEvent` subclass (`TextChunkEvent`, `CompletionDoneEvent`, `BillingEvent`) SHALL have a class-level docstring describing when it is emitted and what its fields represent.

#### Scenario: TextChunkEvent docstring
- **WHEN** a developer inspects `TextChunkEvent`
- **THEN** a docstring is present stating it carries a partial text delta emitted during streaming, with `text` containing the incremental string fragment

#### Scenario: CompletionDoneEvent docstring
- **WHEN** a developer inspects `CompletionDoneEvent`
- **THEN** a docstring is present stating it is always the last event in the stream, carries final metadata (`provider`, `model`, `tokens_usage`, `stop_reason`, `elapsed_s`)

#### Scenario: BillingEvent docstring
- **WHEN** a developer inspects `BillingEvent`
- **THEN** a docstring is present stating it is emitted by adapters that can compute cost, carries `base_input_tokens_cost`, `output_tokens_cost`, and `total_cost` in USD, and its presence is optional

### Requirement: Streaming event ordering is a normative contract
The `acompletion` async generator SHALL guarantee the following event ordering: zero or more `TextChunkEvent` events, followed by an optional `BillingEvent`, followed by exactly one `CompletionDoneEvent` as the terminal event. No events SHALL be emitted after `CompletionDoneEvent`.

#### Scenario: Adapter emits events in correct order
- **WHEN** a conforming adapter yields events from `acompletion`
- **THEN** all `TextChunkEvent` items appear before any `BillingEvent` or `CompletionDoneEvent`, `BillingEvent` (if present) appears immediately before `CompletionDoneEvent`, and `CompletionDoneEvent` is the last item yielded

#### Scenario: Non-streaming path still emits CompletionDoneEvent
- **WHEN** `is_stream_prefered` is `False` and the adapter uses a non-streaming API call
- **THEN** the generator still yields exactly one `CompletionDoneEvent` as its final (and potentially only) event

### Requirement: ILlmPort usage patterns are documented in the spec
The spec SHALL describe the two primary usage contexts: (1) `Session.astream_completion` — where the domain entity calls `acompletion` to stream a reply to the user; (2) `MessageContextStrategy` subclasses — where strategies may call `acompletion` internally to produce summaries for context compression.

#### Scenario: Usage context 1 — Session streaming
- **WHEN** a developer reads the spec
- **THEN** they understand that `Session` holds an `ILlmPort` instance injected at construction and calls `acompletion` with the full message history and session `CompletionConfig`

#### Scenario: Usage context 2 — Context strategy summarization
- **WHEN** a developer reads the spec
- **THEN** they understand that `SummaryStrategy` calls `acompletion` to produce a summary string from overflowing messages, using the strategy's own `CompletionConfig`
