## MODIFIED Requirements

### Requirement: Session.message_context_strategy property

`Session` SHALL expose a read-only `message_context_strategy` property that returns the current `MessageContextStrategy` instance. This allows external code (adapters, use cases) to read strategy state via `strategy_type`, `get_metadata()`, `get_history()`, and `completion_config` without the domain needing to know about DTOs. The property SHALL NOT expose a `get_records()` method; callers that previously used `get_records()` SHALL switch to `get_history()` — the new name for the raw-record view.

#### Scenario: property returns the strategy instance

- **WHEN** `session.message_context_strategy` is accessed
- **THEN** it returns the `MessageContextStrategy` instance passed to the constructor (or built by `create()`)

#### Scenario: strategy state is readable through the property

- **WHEN** `session.message_context_strategy.strategy_type` is accessed
- **THEN** it returns the string identifier of the active strategy (e.g. `"dummy"`)

#### Scenario: raw records are readable via get_history

- **WHEN** `session.message_context_strategy.get_history()` is called
- **THEN** it returns a `list[MessageRecord]` containing every record currently held by the strategy

---

### Requirement: Session.acompletion streaming LLM interaction

`Session.acompletion(prompt, is_stream_prefered)` is an async generator. It SHALL: (1) call `_usage_stats.begin_invocation()` to reset per-request statistics, (2) add the user prompt to the context strategy, (3) retrieve the current LLM-facing context from the strategy via `get_context()`, (4) stream the LLM response via `_llm_stats.acompletion` (the `LlmStatsDecorator`) — yielding `SessionTextChunkEvent` for each `TextChunkEvent`, (5) on `CompletionDoneEvent`, capture the stop reason, (6) add the assembled assistant response to the strategy, (7) yield a final `SessionCompletionDoneEvent` with the stop reason, elapsed time, and `_usage_stats.current_invocation_data`.

`acompletion` SHALL NOT call `get_history()` for the purpose of building the LLM request — `get_history()` returns the persistence shape (`list[MessageRecord]`), not the LLM-facing shape.

#### Scenario: acompletion uses LlmStatsDecorator instead of raw ILlmPort

- **WHEN** `acompletion` is called
- **THEN** it calls `_llm_stats.acompletion(...)`, not `_llm.acompletion(...)`

#### Scenario: acompletion uses get_context to build the LLM request

- **WHEN** `acompletion` is called
- **THEN** the message list passed to `_llm_stats.acompletion` is the value returned by `self._message_context_strategy.get_context()`, not `get_history()`

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
- **THEN** the strategy's history (via `get_history()`) contains a user record with content `"question"` followed by an assistant record with the concatenated LLM response

#### Scenario: session statistics are updated after completion

- **WHEN** `acompletion` completes
- **THEN** `session.statistics` is truthy (non-empty `SessionUsageStats`)

#### Scenario: multiple completions accumulate statistics

- **WHEN** `acompletion` is called twice with 10 prompt tokens each
- **THEN** the cumulative lifecycle stats show 20 prompt tokens total

---

### Requirement: Session.set_message_context_strategy strategy replacement

`Session.set_message_context_strategy(strategy)` SHALL replace the current strategy with a newly-built instance of the provided strategy type, carrying over all existing records from the current strategy. Existing records SHALL be fetched via `self._message_context_strategy.get_history()` — the new raw-record accessor that replaces the removed `get_records()`. The new strategy SHALL be reconstructed via `MessageContextStrategyFactory.build()` so that `_apply_strategy()` runs immediately on the transplanted records.

#### Scenario: strategy type is switched

- **WHEN** `set_message_context_strategy` is called with a `SlidingWindowStrategy`
- **THEN** `session.message_context_strategy.strategy_type` is `"sliding_window"`

#### Scenario: existing records are preserved after strategy switch

- **WHEN** one completion has been recorded and `set_message_context_strategy` is called
- **THEN** the new strategy contains the same number of records as before the switch (subject to the new strategy's window)

#### Scenario: record transplant uses get_history, not get_records

- **WHEN** a developer inspects `Session.set_message_context_strategy`
- **THEN** the method reads the current strategy's records by calling `get_history()`, not `get_records()`, which no longer exists
