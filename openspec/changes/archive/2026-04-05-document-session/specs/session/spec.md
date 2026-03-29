## ADDED Requirements

### Requirement: update_statistics accumulates token usage and cost
`update_statistics(usage_statistics, model_pricing, provider, model, prompt_tokens, completion_tokens)` SHALL mutate `usage_statistics` in place. The key format is `"<provider>,<model>"`. On first encounter for a key it SHALL create a new `UsageStatistics` entry. On subsequent calls for the same key it SHALL add token counts to existing totals and add cost values to existing cost totals. Each provider/model pair is tracked independently.

#### Scenario: new key creates UsageStatistics entry
- **WHEN** `update_statistics` is called with a provider/model pair not yet in the dict
- **THEN** a new entry is created at key `"<provider>,<model>"` with the given token counts

#### Scenario: existing key accumulates token counts
- **WHEN** `update_statistics` is called twice for the same provider/model
- **THEN** `tokens_usage.prompt_tokens` and `tokens_usage.completion_tokens` are the sum of both calls

#### Scenario: cost is accumulated correctly for existing key
- **WHEN** `update_statistics` is called twice with non-zero input tokens for the same key
- **THEN** `tokens_cost.prompt_tokens` equals the sum of the costs for both calls

#### Scenario: output cost is calculated from completion tokens
- **WHEN** `update_statistics` is called with zero prompt tokens and non-zero completion tokens
- **THEN** `tokens_cost.completion_tokens` and `tokens_cost.total_tokens` reflect the completion cost

#### Scenario: multiple provider/model pairs tracked separately
- **WHEN** `update_statistics` is called with two different provider/model combinations
- **THEN** each combination has an independent entry in `usage_statistics`

---

### Requirement: SessionDto persistence model
`SessionDto` is a Pydantic `BaseModel` representing the full serialisable state of a session. It SHALL carry: `id` (non-empty string), `created_at` (datetime), `completion_config`, `statistics` (optional dict keyed by `"provider,model"`), `message_context_strategy_type` (string), `message_context_strategy_metadata` (dict, defaults to `{}`), `message_context_strategy_completion_config`, and `message_records` (list of dicts, defaults to `[]`). An empty `id` SHALL be rejected by Pydantic validation.

#### Scenario: empty id raises validation error
- **WHEN** `SessionDto` is constructed with `id=""`
- **THEN** a `pydantic.ValidationError` is raised

#### Scenario: message_records defaults to empty list
- **WHEN** `SessionDto` is constructed without providing `message_records`
- **THEN** `dto.message_records` is `[]`

#### Scenario: statistics defaults to None
- **WHEN** `SessionDto` is constructed without providing `statistics`
- **THEN** `dto.statistics` is `None`

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
`SessionCompletionDoneEvent` is a Pydantic model with `type` fixed to `"session_completion_done"`, a `stop_reason` (from `StopReason`), `elapsed_s` (non-negative int), and `statistics` (optional dict of `UsageStatistics` for this request only). It is the last event yielded by `Session.acompletion`. `statistics` SHALL reflect token usage for the current request only, not the cumulative session total.

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

---

### Requirement: Session.create factory
`Session.create(llm, id, model_pricing, completion_config, message_context_strategy)` SHALL construct a new `Session` with `created_at` set to the current datetime and `statistics` initialised to an empty dict. The provided `message_context_strategy` is used as-is and its token-usage handler is wired to the session's internal `_handle_token_usage` immediately.

#### Scenario: id is stored as-is
- **WHEN** `Session.create` is called with `id="sess-1"`
- **THEN** `session.id` is `"sess-1"`

#### Scenario: created_at is a datetime
- **WHEN** `Session.create` is called
- **THEN** `session.created_at` is an instance of `datetime`

#### Scenario: completion_config is stored and accessible
- **WHEN** `Session.create` is called with a `CompletionConfig`
- **THEN** `session.completion_config` is the same object

#### Scenario: statistics starts empty
- **WHEN** `Session.create` is called
- **THEN** `session.statistics` is `{}`

#### Scenario: messages starts empty
- **WHEN** `Session.create` is called
- **THEN** `session.messages` is `[]`

---

### Requirement: Session.to_dto serialisation
`Session.to_dto()` SHALL return a `SessionDto` that captures the full session state. The `message_records` list SHALL contain one dict per record with keys `"id"` (string UUID), `"prev_id"` (string UUID or `None`), and `"message"` (role/content dict). The `message_context_strategy_type` SHALL match the current strategy's `strategy_type`.

#### Scenario: to_dto returns a SessionDto instance
- **WHEN** `session.to_dto()` is called
- **THEN** the result is an instance of `SessionDto`

#### Scenario: to_dto preserves session id
- **WHEN** `session.to_dto()` is called
- **THEN** `dto.id` equals `session.id`

#### Scenario: to_dto captures current strategy type
- **WHEN** the session uses `DummyStrategy`
- **THEN** `dto.message_context_strategy_type` is `"dummy"`

#### Scenario: to_dto message_records is a list
- **WHEN** `session.to_dto()` is called
- **THEN** `dto.message_records` is a list

---

### Requirement: Session.from_dto deserialisation
`Session.from_dto(llm, model_pricing, dto)` SHALL reconstruct a `Session` from a `SessionDto`. It SHALL deserialise `message_records` into `MessageRecord` `NamedTuple`s (converting string UUIDs back to `UUID` objects) and restore the strategy via `MessageContextStrategyFactory.build()`. An unknown `message_context_strategy_type` in the DTO SHALL raise `ValueError` (propagated from the factory).

#### Scenario: from_dto preserves session id
- **WHEN** a session is serialised with `to_dto()` and restored with `from_dto()`
- **THEN** `restored.id` equals the original `session.id`

#### Scenario: from_dto preserves created_at
- **WHEN** a session is serialised and restored
- **THEN** `restored.created_at` equals the original `session.created_at`

#### Scenario: from_dto restores message records
- **WHEN** a session has two records (user + assistant) and is round-tripped through `to_dto` / `from_dto`
- **THEN** the restored strategy has exactly two records

#### Scenario: from_dto raises on unknown strategy type
- **WHEN** `dto.message_context_strategy_type` is a value not recognised by the factory
- **THEN** `from_dto` raises `ValueError` with a message containing "Unknown strategy type"

---

### Requirement: Session.acompletion streaming LLM interaction
`Session.acompletion(prompt, is_stream_prefered)` is an async generator. It SHALL: (1) reset per-request statistics, (2) add the user prompt to the context strategy, (3) retrieve the current history from the strategy, (4) stream the LLM response — yielding `SessionTextChunkEvent` for each text chunk, (5) add the assembled assistant response to the strategy, (6) yield a final `SessionCompletionDoneEvent` with the stop reason, elapsed time, and per-request statistics.

#### Scenario: user and assistant messages are appended to strategy
- **WHEN** `acompletion("question", False)` completes
- **THEN** the strategy's records contain a user record with content `"question"` followed by an assistant record with the concatenated LLM response

#### Scenario: session statistics are updated after completion
- **WHEN** `acompletion` completes
- **THEN** `session.statistics` is non-empty

#### Scenario: multiple completions accumulate statistics
- **WHEN** `acompletion` is called twice with 10 prompt tokens each
- **THEN** the cumulative `session.statistics` entry shows 20 prompt tokens total

---

### Requirement: Session.set_message_context_strategy strategy replacement
`Session.set_message_context_strategy(strategy)` SHALL replace the current strategy with a newly-built instance of the provided strategy type, carrying over all existing records from the current strategy. The new strategy SHALL be reconstructed via `MessageContextStrategyFactory.build()` so that `_apply_strategy()` runs immediately on the transplanted records. The new strategy SHALL have its token-usage handler wired to the session.

#### Scenario: strategy type is switched
- **WHEN** `set_message_context_strategy` is called with a `SlidingWindowStrategy`
- **THEN** `session._message_context_strategy.strategy_type` is `"sliding_window"`

#### Scenario: existing records are preserved after strategy switch
- **WHEN** one completion has been recorded and `set_message_context_strategy` is called
- **THEN** the new strategy contains the same number of records as before the switch (subject to the new strategy's window)

#### Scenario: new strategy still receives token usage events
- **WHEN** `set_message_context_strategy` is called and then `acompletion` is invoked
- **THEN** `session.statistics` is updated (token usage handler wired correctly)
