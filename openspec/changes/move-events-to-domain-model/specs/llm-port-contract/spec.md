## MODIFIED Requirements

### Requirement: ILlmPort interface is documented with purpose and contract

`ILlmPort` SHALL be a `typing.Protocol` (not an ABC) defining the contract for LLM completion providers. The domain layer depends only on this interface, never on concrete SDK types. Implementors satisfy the protocol through structural subtyping — they do not need to inherit from `ILlmPort`. The protocol defines a single method: `acompletion`.

Event types (`CompletionEvent`, `TextChunkEvent`, `CompletionDoneEvent`) SHALL be defined in `server/application/domain/model/llm_events.py`, not in the port module. The port module `server/application/port/outbound/llm_port.py` SHALL import these event types from the domain model layer and MAY re-export them for backward compatibility.

#### Scenario: Class is a Protocol

- **WHEN** a developer inspects `ILlmPort` in `server/application/port/outbound/llm_port.py`
- **THEN** it inherits from `typing.Protocol`, not `abc.ABC`

#### Scenario: Structural subtyping works

- **WHEN** a class implements `acompletion` with a matching signature without inheriting from `ILlmPort`
- **THEN** mypy accepts it wherever `ILlmPort` is expected

#### Scenario: Event types live in domain model

- **WHEN** a developer inspects the source of `CompletionEvent`, `TextChunkEvent`, `CompletionDoneEvent`
- **THEN** they are defined in `server/application/domain/model/llm_events.py`

#### Scenario: Domain model does not import from port

- **WHEN** analyzing imports in any file under `server/application/domain/model/`
- **THEN** no import references `server.application.port`

### Requirement: Streaming event ordering is a normative contract

The `acompletion` async generator SHALL guarantee the following event ordering: zero or more `TextChunkEvent` events, followed by exactly one `CompletionDoneEvent` as the terminal event. No events SHALL be emitted after `CompletionDoneEvent`.

#### Scenario: Adapter emits events in correct order

- **WHEN** a conforming adapter yields events from `acompletion`
- **THEN** all `TextChunkEvent` items appear before `CompletionDoneEvent`, and `CompletionDoneEvent` is the last item yielded

#### Scenario: Non-streaming path still emits CompletionDoneEvent

- **WHEN** `is_stream_prefered` is `False` and the adapter uses a non-streaming API call
- **THEN** the generator still yields exactly one `CompletionDoneEvent` as its final (and potentially only) event
