## MODIFIED Requirements

### Requirement: Session construction
`Session.__init__` SHALL accept the following parameters: `llm` (an `ILlmPort` for the session's own completions), `id` (str), `created_at` (datetime), `completion_config` (CompletionConfig), `statistics` (optional `dict[str, dict[str, ModelStats]]`), `billing` (optional `ModelBilling`), `strategy_type` (str), `strategy_metadata` (dict), `strategy_records` (list of MessageRecord), `strategy_llm` (an `ILlmPort` for the strategy's completions), `strategy_completion_config` (CompletionConfig), and `strategy_billing` (optional `ModelBilling`). The constructor SHALL:
1. Create a `SessionUsageStats(data=statistics)` and store it as `_usage_stats`.
2. Create a `LlmStatsDecorator(llm=llm, usage_stats=_usage_stats, billing=billing)` and store it as `_llm_stats` for session completions.
3. Create a `LlmStatsDecorator(llm=strategy_llm, usage_stats=_usage_stats, billing=strategy_billing)` for strategy completions.
4. Build the `MessageContextStrategy` via `MessageContextStrategyFactory.build(strategy_type, strategy_metadata, strategy_records, strategy_llm_stats_decorator, strategy_completion_config)` and store it as `_message_context_strategy`.

#### Scenario: Session creates SessionUsageStats from statistics parameter
- **WHEN** `Session` is constructed with `statistics={"anthropic": {"claude-3": ModelStats(...)}}`
- **THEN** `session._usage_stats` is a `SessionUsageStats` initialized with that data

#### Scenario: Session creates two LlmStatsDecorators sharing the same SessionUsageStats
- **WHEN** `Session` is constructed
- **THEN** both the session's and the strategy's `LlmStatsDecorator` reference the same `SessionUsageStats` instance

#### Scenario: Session without billing creates decorator with billing=None
- **WHEN** `Session` is constructed with `billing=None`
- **THEN** the session's `LlmStatsDecorator` has `billing=None`

---

### Requirement: Session.create factory
`Session.create` SHALL accept `llm`, `id`, `completion_config`, `billing`, `strategy_type`, `strategy_metadata`, `strategy_llm`, `strategy_completion_config`, and `strategy_billing`. It SHALL delegate to `__init__` with `created_at=datetime.now()`, `statistics=None`, and `strategy_records=[]`.

#### Scenario: create produces a Session with empty stats
- **WHEN** `Session.create(...)` is called
- **THEN** `session._usage_stats` is empty (both `current_invocation_data` and `lifecycle_total_data` are empty dicts)

#### Scenario: create sets created_at to now
- **WHEN** `Session.create(...)` is called
- **THEN** `session.created_at` is approximately the current datetime

---

### Requirement: Session.from_dto deserialization
`Session.from_dto` SHALL accept `llm` (ILlmPort), `dto` (SessionDto), `billing` (optional ModelBilling), `strategy_llm` (ILlmPort), and `strategy_billing` (optional ModelBilling). It SHALL extract `strategy_type`, `strategy_metadata`, `strategy_records`, and `strategy_completion_config` from the DTO and delegate to `__init__`.

#### Scenario: from_dto restores SessionUsageStats from dto.statistics
- **WHEN** `dto.statistics` contains data
- **THEN** the restored session's `_usage_stats.lifecycle_total_data` matches the DTO statistics

#### Scenario: from_dto passes billing to constructor
- **WHEN** `billing` is provided to `from_dto`
- **THEN** the session's `LlmStatsDecorator` uses that `ModelBilling`

---

### Requirement: Session.to_dto serialization
`Session.to_dto()` SHALL return a `SessionDto` with `statistics` set to `self._usage_stats.lifecycle_total_data or None`.

#### Scenario: to_dto uses lifecycle_total_data for statistics
- **WHEN** `session.to_dto()` is called after completions have accumulated stats
- **THEN** `dto.statistics` reflects the lifecycle total, not the current invocation

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

---

### Requirement: Session statistics property
`Session.statistics` SHALL return `self._usage_stats` (the `SessionUsageStats` instance).

#### Scenario: statistics returns SessionUsageStats
- **WHEN** `session.statistics` is accessed
- **THEN** it returns a `SessionUsageStats` instance

## REMOVED Requirements

### Requirement: Session._handle_token_usage
**Reason**: Token usage handling is now performed by `LlmStatsDecorator`. The `_handle_token_usage` method and the `_request_statistics` member are no longer needed.
**Migration**: Remove `_handle_token_usage` method. Remove `_request_statistics` member. Both are replaced by `SessionUsageStats` + `LlmStatsDecorator`.
