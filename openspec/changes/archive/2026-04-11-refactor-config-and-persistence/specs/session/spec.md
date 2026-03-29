## ADDED Requirements

### Requirement: SessionState domain data model
`SessionState` is a plain data class (Pydantic `BaseModel` or `dataclass`) representing the full serializable snapshot of a session's state. It SHALL carry: `id` (non-empty string), `created_at` (datetime), `completion_config` (CompletionConfig), `statistics` (optional `dict[str, dict[str, ModelStats]]`, defaults to `None`), `strategy_type` (string), `strategy_metadata` (dict, defaults to `{}`), `strategy_completion_config` (CompletionConfig), and `strategy_records` (list of `MessageRecord`, defaults to `[]`). `SessionState` is defined in the domain layer and used by `ISessionRepository` as the return type for `get_session()`.

#### Scenario: SessionState carries all session fields
- **WHEN** a `SessionState` is constructed with all fields
- **THEN** all fields are accessible and match the provided values

#### Scenario: strategy_records defaults to empty list
- **WHEN** `SessionState` is constructed without providing `strategy_records`
- **THEN** `state.strategy_records` is `[]`

#### Scenario: statistics defaults to None
- **WHEN** `SessionState` is constructed without providing `statistics`
- **THEN** `state.statistics` is `None`

---

### Requirement: Session.message_context_strategy property
`Session` SHALL expose a read-only `message_context_strategy` property that returns the current `MessageContextStrategy` instance. This allows external code (adapters, use cases) to read strategy state via `strategy_type`, `get_metadata()`, `get_records()`, and `completion_config` without the domain needing to know about DTOs.

#### Scenario: property returns the strategy instance
- **WHEN** `session.message_context_strategy` is accessed
- **THEN** it returns the `MessageContextStrategy` instance passed to the constructor (or built by `create()`)

#### Scenario: strategy state is readable through the property
- **WHEN** `session.message_context_strategy.strategy_type` is accessed
- **THEN** it returns the string identifier of the active strategy (e.g. `"dummy"`)

---

## MODIFIED Requirements

### Requirement: Session construction
`Session.__init__` SHALL accept the following parameters: `llm` (an `ILlmPort` for the session's own completions), `id` (str), `created_at` (datetime), `completion_config` (CompletionConfig), `billing` (optional `ModelBilling`), `usage_stats` (`SessionUsageStats`), and `message_context_strategy` (a pre-built `MessageContextStrategy` instance). The constructor SHALL:
1. Store `_usage_stats` from the provided `usage_stats` parameter.
2. Create a `LlmStatsDecorator(llm=llm, usage_stats=_usage_stats, billing=billing)` and store it as `_llm_stats` for session completions.
3. Store the provided `message_context_strategy` as `_message_context_strategy`.

The constructor SHALL NOT build the strategy internally — it receives a pre-built instance. The constructor SHALL NOT create `SessionUsageStats` — it receives a pre-built instance.

#### Scenario: Session stores the provided usage_stats
- **WHEN** `Session` is constructed with a `SessionUsageStats` instance containing data
- **THEN** `session.statistics` returns that same `SessionUsageStats` instance

#### Scenario: Session stores the provided message_context_strategy
- **WHEN** `Session` is constructed with a `DummyStrategy` instance
- **THEN** `session.message_context_strategy` returns that same instance

#### Scenario: Session creates LlmStatsDecorator from llm and usage_stats
- **WHEN** `Session` is constructed
- **THEN** the session's `LlmStatsDecorator` references the provided `usage_stats`

#### Scenario: Session without billing creates decorator with billing=None
- **WHEN** `Session` is constructed with `billing=None`
- **THEN** the session's `LlmStatsDecorator` has `billing=None`

---

### Requirement: Session.create factory
`Session.create` SHALL be an async classmethod that accepts `llm`, `id`, `completion_config`, `billing`, `strategy_type`, `strategy_metadata`, `strategy_llm`, `strategy_completion_config`, and `strategy_billing`. It SHALL:
1. Create a new `SessionUsageStats()`.
2. Create a `LlmStatsDecorator(llm=strategy_llm, usage_stats=usage_stats, billing=strategy_billing)` for the strategy's LLM.
3. Build the strategy via `MessageContextStrategyFactory.build(strategy_type, strategy_metadata, [], strategy_llm_stats, strategy_completion_config)`.
4. Delegate to `__init__` with `created_at=datetime.now()` and the built strategy and usage_stats.

#### Scenario: create produces a Session with empty stats
- **WHEN** `Session.create(...)` is called
- **THEN** `session.statistics` is empty (both `current_invocation_data` and `lifecycle_total_data` are empty dicts)

#### Scenario: create sets created_at to now
- **WHEN** `Session.create(...)` is called
- **THEN** `session.created_at` is approximately the current datetime

#### Scenario: create builds strategy via factory
- **WHEN** `Session.create(...)` is called with `strategy_type="sliding_window"` and `strategy_metadata={"window_size": 4}`
- **THEN** `session.message_context_strategy.strategy_type` is `"sliding_window"`

---

### Requirement: Session statistics property
`Session.statistics` SHALL return `self._usage_stats` (the `SessionUsageStats` instance). The property exposes the full `SessionUsageStats` object, not just a dict — callers can access `lifecycle_total_data`, `current_invocation_data`, and `begin_invocation()` through it.

#### Scenario: statistics returns SessionUsageStats
- **WHEN** `session.statistics` is accessed
- **THEN** it returns a `SessionUsageStats` instance

---

### Requirement: Session.acompletion streaming LLM interaction
`Session.acompletion(prompt, is_stream_prefered)` is an async generator. It SHALL: (1) call `_usage_stats.begin_invocation()` to reset per-request statistics, (2) add the user prompt to the context strategy, (3) retrieve the current history from the strategy, (4) stream the LLM response via `_llm_stats.acompletion` (the `LlmStatsDecorator`) — yielding `SessionTextChunkEvent` for each `TextChunkEvent`, (5) on `CompletionDoneEvent`, capture the stop reason, (6) add the assembled assistant response to the strategy, (7) yield a final `SessionCompletionDoneEvent` with the stop reason, elapsed time, and `_usage_stats.current_invocation_data`.

#### Scenario: acompletion uses LlmStatsDecorator instead of raw ILlmPort
- **WHEN** `acompletion` is called
- **THEN** it calls `_llm_stats.acompletion(...)`, not `_llm.acompletion(...)`

#### Scenario: begin_invocation is called before each completion
- **WHEN** `acompletion` is called
- **THEN** `_usage_stats.begin_invocation()` is called before the LLM request

#### Scenario: done event statistics use current_invocation_data
- **WHEN** `acompletion` completes
- **THEN** `SessionCompletionDoneEvent.statistics` equals `_usage_stats.current_invocation_data or None`

#### Scenario: session does not handle BillingEvent
- **WHEN** `acompletion` processes the LLM event stream
- **THEN** there is no code referencing `BillingEvent` — billing is handled by `LlmStatsDecorator`

#### Scenario: user and assistant messages are appended to strategy
- **WHEN** `acompletion("question", False)` completes
- **THEN** the strategy's records contain a user record with content `"question"` followed by an assistant record with the concatenated LLM response

#### Scenario: session statistics are updated after completion
- **WHEN** `acompletion` completes
- **THEN** `session.statistics` is truthy (non-empty `SessionUsageStats`)

#### Scenario: multiple completions accumulate statistics
- **WHEN** `acompletion` is called twice with 10 prompt tokens each
- **THEN** the cumulative lifecycle stats show 20 prompt tokens total

---

### Requirement: Session.set_message_context_strategy strategy replacement
`Session.set_message_context_strategy(strategy)` SHALL replace the current strategy with a newly-built instance of the provided strategy type, carrying over all existing records from the current strategy. The new strategy SHALL be reconstructed via `MessageContextStrategyFactory.build()` so that `_apply_strategy()` runs immediately on the transplanted records.

#### Scenario: strategy type is switched
- **WHEN** `set_message_context_strategy` is called with a `SlidingWindowStrategy`
- **THEN** `session.message_context_strategy.strategy_type` is `"sliding_window"`

#### Scenario: existing records are preserved after strategy switch
- **WHEN** one completion has been recorded and `set_message_context_strategy` is called
- **THEN** the new strategy contains the same number of records as before the switch (subject to the new strategy's window)

---

## REMOVED Requirements

### Requirement: SessionDto persistence model
**Reason**: `SessionDto` moves from the domain layer to the adapter layer (`session_file_adapter.py`). The domain no longer defines persistence-specific DTOs; instead, `SessionState` provides the domain's view of serializable state, and the adapter handles format-specific mapping.
**Migration**: Replace domain `SessionDto` usage with `SessionState` in port interfaces. Adapter owns `SessionDto` (or equivalent internal DTOs) for file I/O.

### Requirement: Session.to_dto serialization
**Reason**: Replaced by `Session` properties. The adapter reads `session.id`, `session.created_at`, `session.completion_config`, `session.statistics`, and `session.message_context_strategy` (with its `.strategy_type`, `.get_metadata()`, `.get_records()`, `.completion_config`) directly.
**Migration**: Adapter maps Session properties to its internal DTOs for persistence.

### Requirement: Session.from_dto deserialization
**Reason**: Replaced by direct `Session.__init__` construction. The use case (`GetSessionUseCase`) receives `SessionState` from the repository, builds runtime dependencies (LLM ports, billing, strategy via factory), and calls `Session(...)`.
**Migration**: Use case reconstructs Session from `SessionState` fields + runtime dependencies via constructor.

---

### Requirement: SessionTextChunkEvent streaming event
`SessionTextChunkEvent` is a Pydantic model with `type` fixed to the literal `"session_text_chunk"` and a `text` string field. It is yielded by `Session.acompletion` for each text chunk received from the LLM port.

#### Scenario: text chunk event carries chunk text
- **WHEN** the LLM port yields a `TextChunkEvent` with text "Hello"
- **THEN** `Session.acompletion` yields a `SessionTextChunkEvent` with `text="Hello"`

#### Scenario: multiple chunks are yielded in order
- **WHEN** the LLM port yields two `TextChunkEvent`s with texts "Hello" and " world"
- **THEN** `Session.acompletion` yields two `SessionTextChunkEvent`s in the same order

---

### Requirement: SessionCompletionDoneEvent terminal event
`SessionCompletionDoneEvent` is a Pydantic model with `type` fixed to `"session_completion_done"`, a `stop_reason` (from `StopReason`), `elapsed_s` (non-negative int), and `statistics` (optional `dict[str, dict[str, ModelStats]]` for this request only). It is the last event yielded by `Session.acompletion`. `statistics` SHALL reflect token usage for the current request only, not the cumulative session total.

#### Scenario: done event is the final event yielded
- **WHEN** `Session.acompletion` completes
- **THEN** exactly one `SessionCompletionDoneEvent` is yielded and it is the last event in the stream

#### Scenario: done event carries the LLM stop reason
- **WHEN** the LLM port emits `stop_reason=StopReason.STOP`
- **THEN** `SessionCompletionDoneEvent.stop_reason` is `StopReason.STOP`

#### Scenario: done event statistics are per-request only
- **WHEN** `acompletion` is called and the LLM responds
- **THEN** `SessionCompletionDoneEvent.statistics` is non-None and reflects only the tokens used in that single request

#### Scenario: elapsed_s is non-negative
- **WHEN** `acompletion` completes
- **THEN** `SessionCompletionDoneEvent.elapsed_s` is greater than or equal to zero
