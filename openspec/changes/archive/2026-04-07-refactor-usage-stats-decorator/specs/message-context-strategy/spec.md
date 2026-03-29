## MODIFIED Requirements

### Requirement: MessageContextStrategy abstract interface
`MessageContextStrategy` is an abstract base class that defines the contract for all conversation-history management strategies. The constructor SHALL accept `llm` (an object satisfying `ILlmPort` Protocol), `completion_config` (CompletionConfig), and optional `records` (list of MessageRecord). It SHALL NOT have any token usage handler mechanism — no `OnTokenUsage`, no `_emit_token_usage`, no `_token_usage_handlers`. Token usage tracking is handled externally by `LlmStatsDecorator`.

Concrete subclasses SHALL implement `strategy_type` (str property), `get_metadata()` (returns a JSON-serialisable dict of strategy state), `_apply_strategy()` (async, called after every message addition), and `_get_history()` (returns the ordered list of message dicts to include in the next LLM call, without the system prompt).

#### Scenario: add_user_query appends a user-role record
- **WHEN** `add_user_query(content)` is called
- **THEN** a new `MessageRecord` with `role="user"` and the given content is appended to the record list, and `_apply_strategy()` is awaited

#### Scenario: add_model_response appends an assistant-role record
- **WHEN** `add_model_response(content)` is called
- **THEN** a new `MessageRecord` with `role="assistant"` and the given content is appended to the record list, and `_apply_strategy()` is awaited

#### Scenario: get_history prepends system prompt when configured
- **WHEN** `CompletionConfig.system_prompt` is non-empty
- **THEN** `get_history()` returns a list whose first element is `{"role": "system", "content": <system_prompt>}`, followed by the strategy's message window

#### Scenario: get_records returns a defensive copy
- **WHEN** `get_records()` is called multiple times
- **THEN** each call returns a new list object

#### Scenario: no token usage handler mechanism exists
- **WHEN** a developer inspects `MessageContextStrategy`
- **THEN** there is no `OnTokenUsage` method, no `_emit_token_usage` method, no `_token_usage_handlers` member, and no `TokenUsageHandler` type alias

---

### Requirement: SummaryStrategy — LLM-based rolling summary
`SummaryStrategy` SHALL maintain a rolling text summary of older conversation turns produced by the LLM itself. When the record count exceeds `window_size`, `_apply_strategy()` SHALL call the LLM (via `self._llm.acompletion`) with the full message history and store the LLM's response as the new `_summary`, then clear `_records`. The `self._llm` will be a `LlmStatsDecorator` (satisfying `ILlmPort` Protocol), so token usage is tracked automatically — no explicit `_emit_token_usage` call is needed.

#### Scenario: records exceeding window trigger summarisation via self._llm
- **WHEN** the number of records exceeds `window_size`
- **THEN** `self._llm.acompletion` is called, `_summary` is replaced with the LLM response text, and `_records` is cleared

#### Scenario: token usage is tracked by decorator transparently
- **WHEN** summarisation occurs and `self._llm` is a `LlmStatsDecorator`
- **THEN** the decorator intercepts `CompletionDoneEvent` and accumulates stats into `SessionUsageStats` without any explicit call in the strategy

#### Scenario: no _emit_token_usage call in _apply_strategy
- **WHEN** a developer inspects `SummaryStrategy._apply_strategy`
- **THEN** there is no call to `_emit_token_usage` — the decorator handles stats accumulation

---

### Requirement: MessageContextStrategyFactory — build and restore strategies
`MessageContextStrategyFactory.build(strategy_type, metadata, records, llm, completion_config)` SHALL reconstruct a strategy from its serialised state. The `llm` parameter is an `ILlmPort`-compatible object (which will be a `LlmStatsDecorator` when called from Session). `default(llm, completion_config)` SHALL return a `DummyStrategy` with no records.

#### Scenario: build passes llm to strategy constructor
- **WHEN** `build("summary", metadata, records, llm_stats_decorator, config)` is called
- **THEN** the created `SummaryStrategy` stores `llm_stats_decorator` as its `_llm`

#### Scenario: build with unknown type raises ValueError
- **WHEN** `build("nonexistent", {}, [], llm, config)` is called
- **THEN** a `ValueError` is raised with a message containing "Unknown strategy type"

## REMOVED Requirements

### Requirement: TokenUsageHandler callable type
**Reason**: `TokenUsageHandler`, `OnTokenUsage()`, and `_emit_token_usage()` are removed. Token usage tracking is now handled externally by `LlmStatsDecorator` wrapping the LLM port.
**Migration**: Remove `TokenUsageHandler` type alias, `OnTokenUsage()` method, `_emit_token_usage()` method, and `_token_usage_handlers` member from `MessageContextStrategy`. The strategy's `_llm` will be a `LlmStatsDecorator` that handles stats accumulation transparently.
