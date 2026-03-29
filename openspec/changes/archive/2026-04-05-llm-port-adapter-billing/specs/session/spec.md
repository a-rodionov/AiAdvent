## MODIFIED Requirements

### Requirement: update_statistics accumulates token usage and cost
`update_statistics(usage_statistics, provider, model, prompt_tokens, completion_tokens, base_input_tokens_cost, output_tokens_cost, total_cost)` SHALL mutate `usage_statistics` in place. The key format is `"<provider>,<model>"`. On first encounter for a key it SHALL create a new `UsageStatistics` entry. On subsequent calls for the same key it SHALL add token counts to existing totals and add cost values to existing cost totals. Each provider/model pair is tracked independently. The function SHALL NOT call `ModelPricing.estimate()` or accept a `model_pricing` argument — all cost values are supplied by the caller as pre-computed floats.

#### Scenario: new key creates UsageStatistics entry
- **WHEN** `update_statistics` is called with a provider/model pair not yet in the dict
- **THEN** a new entry is created at key `"<provider>,<model>"` with the given token counts

#### Scenario: existing key accumulates token counts
- **WHEN** `update_statistics` is called twice for the same provider/model
- **THEN** `tokens_usage.prompt_tokens` and `tokens_usage.completion_tokens` are the sum of both calls

#### Scenario: cost is accumulated directly from supplied arguments
- **WHEN** `update_statistics` is called twice with `base_input_tokens_cost=0.001` each time for the same key
- **THEN** `tokens_cost.prompt_tokens` equals `0.002`

#### Scenario: output cost is accumulated from supplied argument
- **WHEN** `update_statistics` is called with `output_tokens_cost=0.004`
- **THEN** `tokens_cost.completion_tokens` equals `0.004`

#### Scenario: total cost is accumulated directly from supplied argument
- **WHEN** `update_statistics` is called with `total_cost=0.005`
- **THEN** `tokens_cost.total_tokens` equals `0.005`

#### Scenario: multiple provider/model pairs tracked separately
- **WHEN** `update_statistics` is called with two different provider/model combinations
- **THEN** each combination has an independent entry in `usage_statistics`

---

### Requirement: Session.create factory
`Session.create(llm, id, completion_config, message_context_strategy)` SHALL construct a new `Session` with `created_at` set to the current datetime and `statistics` initialised to an empty dict. The `model_pricing` parameter is removed — `Session` no longer holds a pricing reference. The provided `message_context_strategy` is used as-is and its token-usage handler is wired to the session's internal `_handle_token_usage` immediately.

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

### Requirement: Session.from_dto deserialisation
`Session.from_dto(llm, dto)` SHALL reconstruct a `Session` from a `SessionDto`. The `model_pricing` parameter is removed. It SHALL deserialise `message_records` into `MessageRecord` `NamedTuple`s (converting string UUIDs back to `UUID` objects) and restore the strategy via `MessageContextStrategyFactory.build()`. An unknown `message_context_strategy_type` in the DTO SHALL raise `ValueError` (propagated from the factory).

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
`Session.acompletion(prompt, is_stream_prefered)` is an async generator. It SHALL: (1) reset per-request statistics, (2) add the user prompt to the context strategy, (3) retrieve the current history from the strategy, (4) stream the LLM response — yielding `SessionTextChunkEvent` for each text chunk, (5) capture any `BillingEvent` encountered in the stream, (6) add the assembled assistant response to the strategy, (7) call `_handle_token_usage` with token counts from `CompletionDoneEvent` and cost fields from the `BillingEvent` if one was captured (defaulting all costs to `0.0` when absent), (8) yield a final `SessionCompletionDoneEvent` with the stop reason, elapsed time, and per-request statistics.

#### Scenario: user and assistant messages are appended to strategy
- **WHEN** `acompletion("question", False)` completes
- **THEN** the strategy's records contain a user record with content `"question"` followed by an assistant record with the concatenated LLM response

#### Scenario: session statistics are updated after completion
- **WHEN** `acompletion` completes
- **THEN** `session.statistics` is non-empty

#### Scenario: multiple completions accumulate statistics
- **WHEN** `acompletion` is called twice with 10 prompt tokens each
- **THEN** the cumulative `session.statistics` entry shows 20 prompt tokens total

#### Scenario: BillingEvent in stream causes statistics to use billing costs
- **WHEN** `acompletion` completes and a `BillingEvent` with `total_cost=0.05` was in the stream
- **THEN** `session.statistics` for that provider/model shows `tokens_cost.total_tokens=0.05`

#### Scenario: no BillingEvent in stream results in zero costs in statistics
- **WHEN** `acompletion` completes and no `BillingEvent` was in the stream
- **THEN** `session.statistics` for that provider/model shows `tokens_cost.total_tokens=0.0`
