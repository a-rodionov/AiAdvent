## REMOVED Requirements

### Requirement: update_statistics accumulates token usage and cost
**Reason**: Replaced by `UsageStats.add_stats()`. Accumulation logic is now encapsulated in the `UsageStats` value object; `Session` calls `add_stats` directly on its `UsageStats` members.
**Migration**: Replace all calls to `update_statistics(dict, ...)` with `usage_stats.add_stats(provider, model, usage, cost)`.

---

## MODIFIED Requirements

### Requirement: SessionDto persistence model
`SessionDto` is a Pydantic `BaseModel` representing the full serialisable state of a session. It SHALL carry: `id` (non-empty string), `created_at` (datetime), `completion_config`, `statistics` (optional `dict[str, dict[str, ModelStats]]` keyed by provider then model, defaults to `None`), `message_context_strategy_type` (string), `message_context_strategy_metadata` (dict, defaults to `{}`), `message_context_strategy_completion_config`, and `message_records` (list of dicts, defaults to `[]`). An empty `id` SHALL be rejected by Pydantic validation.

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

---

### Requirement: Session.create factory
`Session.create(llm, id, completion_config, message_context_strategy)` SHALL construct a new `Session` with `created_at` set to the current datetime and `_statistics` initialised to an empty `UsageStats()`. The provided `message_context_strategy` is used as-is and its token-usage handler is wired to the session's internal `_handle_token_usage` immediately.

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
- **THEN** `session.statistics` is falsy (empty `UsageStats`)

#### Scenario: messages starts empty
- **WHEN** `Session.create` is called
- **THEN** `session.messages` is `[]`

---

### Requirement: Session.acompletion streaming LLM interaction
`Session.acompletion(prompt, is_stream_prefered)` is an async generator. It SHALL: (1) reset per-request statistics via `_request_statistics.zero()`, (2) add the user prompt to the context strategy, (3) retrieve the current history from the strategy, (4) stream the LLM response — yielding `SessionTextChunkEvent` for each text chunk, (5) capture any `BillingEvent` encountered in the stream, (6) add the assembled assistant response to the strategy, (7) call `_handle_token_usage` with token counts from `CompletionDoneEvent` and a `TokensCost` built from the `BillingEvent` if one was captured, or `cost=None` when no `BillingEvent` was present, (8) yield a final `SessionCompletionDoneEvent` with the stop reason, elapsed time, and per-request statistics.

#### Scenario: user and assistant messages are appended to strategy
- **WHEN** `acompletion("question", False)` completes
- **THEN** the strategy's records contain a user record with content `"question"` followed by an assistant record with the concatenated LLM response

#### Scenario: session statistics are updated after completion
- **WHEN** `acompletion` completes
- **THEN** `session.statistics` is truthy (non-empty `UsageStats`)

#### Scenario: multiple completions accumulate statistics
- **WHEN** `acompletion` is called twice with 10 prompt tokens each
- **THEN** the cumulative `session.statistics` entry shows 20 prompt tokens total

#### Scenario: BillingEvent in stream causes statistics to use billing costs
- **WHEN** `acompletion` completes and a `BillingEvent` with `total_cost=0.05` was in the stream
- **THEN** `session.statistics` for that provider/model shows `cost.total_tokens=0.05`

#### Scenario: no BillingEvent in stream results in None cost in statistics
- **WHEN** `acompletion` completes and no `BillingEvent` was in the stream
- **THEN** `session.statistics` for that provider/model has `cost` equal to `None`
