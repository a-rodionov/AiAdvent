## MODIFIED Requirements

### Requirement: MessageContextStrategy abstract interface
`MessageContextStrategy` is an abstract base class that defines the contract for all conversation-history management strategies. Concrete subclasses SHALL implement `strategy_type` (str property), `get_metadata()` (returns a JSON-serialisable dict of strategy state), `_apply_strategy()` (async, called after every message addition), and `_get_history()` (returns the ordered list of message dicts to include in the next LLM call, without the system prompt).

#### Scenario: add_user_query appends a user-role record
- **WHEN** `add_user_query(content)` is called
- **THEN** a new `MessageRecord` with `role="user"` and the given content is appended to the record list, and `_apply_strategy()` is awaited

#### Scenario: add_model_response appends an assistant-role record
- **WHEN** `add_model_response(content)` is called
- **THEN** a new `MessageRecord` with `role="assistant"` and the given content is appended to the record list, and `_apply_strategy()` is awaited

#### Scenario: get_history prepends system prompt when configured
- **WHEN** `CompletionConfig.system_prompt` is non-empty
- **THEN** `get_history()` returns a list whose first element is `{"role": "system", "content": <system_prompt>}`, followed by the strategy's message window

#### Scenario: get_history has no system message when system_prompt is absent
- **WHEN** `CompletionConfig.system_prompt` is empty or not set
- **THEN** `get_history()` returns only the strategy's message window with no system-role prefix

#### Scenario: get_records returns a defensive copy
- **WHEN** `get_records()` is called multiple times
- **THEN** each call returns a new list object (mutations to the returned list SHALL NOT affect internal state)

#### Scenario: token usage handler is called on summarisation with extended signature
- **WHEN** a `TokenUsageHandler` is registered via `OnTokenUsage()` and a token-producing LLM call occurs inside `_apply_strategy()`
- **THEN** the handler receives `(provider, model, prompt_tokens, completion_tokens, base_input_tokens_cost, output_tokens_cost, total_cost)` matching the LLM response

---

### Requirement: TokenUsageHandler callable type
`TokenUsageHandler` is a `Callable` with signature `(provider: str, model: str, prompt_tokens: int, completion_tokens: int, base_input_tokens_cost: float, output_tokens_cost: float, total_cost: float) -> None`. Registered handlers SHALL be called with all seven positional arguments every time `_emit_token_usage` fires.

#### Scenario: handler receives all seven arguments
- **WHEN** `_emit_token_usage("anthropic", "claude-3", 10, 5, 0.001, 0.003, 0.004)` is called
- **THEN** the registered handler is invoked with exactly those seven values in order

#### Scenario: multiple handlers are each called
- **WHEN** two handlers are registered via `OnTokenUsage()` and `_emit_token_usage` fires
- **THEN** both handlers are called with identical arguments

---

### Requirement: SummaryStrategy — LLM-based rolling summary
`SummaryStrategy` SHALL maintain a rolling text summary of older conversation turns produced by the LLM itself. When the record count exceeds `window_size`, `_apply_strategy()` MUST call the LLM with the full message history (including system prompt and all current records) and store the LLM's response as the new `_summary`, then clear `_records` to an empty list. Its `strategy_type` SHALL be `"summary"`. Its `get_metadata()` SHALL return `{"window_size": <int>, "summary": <str>}`. A `window_size` of 0 or less SHALL raise `ValueError`. A `None` LLM port SHALL raise `ValueError`. After the LLM call, `_emit_token_usage` SHALL be called using cost fields from the `BillingEvent` if one was present in the stream (with `prompt_tokens=0` and `completion_tokens=0`), or with token counts from `CompletionDoneEvent` and all costs `0.0` when no `BillingEvent` was present.

#### Scenario: window_size zero raises ValueError
- **WHEN** `SummaryStrategy` is instantiated with `window_size=0`
- **THEN** a `ValueError` is raised with a message containing "window_size must be >= 1"

#### Scenario: None LLM raises ValueError
- **WHEN** `SummaryStrategy` is instantiated with `llm=None`
- **THEN** a `ValueError` is raised with a message containing "LlmAdapter object is None"

#### Scenario: records within window are not summarised
- **WHEN** the number of records is less than or equal to `window_size`
- **THEN** no LLM call is made, records are unchanged, and the summary is unchanged

#### Scenario: records exceeding window trigger summarisation
- **WHEN** the number of records exceeds `window_size`
- **THEN** the LLM is called, `_summary` is replaced with the LLM response text, and `_records` is cleared to an empty list

#### Scenario: existing summary is prepended to history as a user-role message
- **WHEN** `_get_history()` is called and `_summary` is non-empty
- **THEN** the first element of the returned list is `{"role": "user", "content": <summary>}`, followed by the current records

#### Scenario: empty summary is omitted from history
- **WHEN** `_get_history()` is called and `_summary` is an empty string
- **THEN** the returned list contains only the current records, with no injected summary entry

#### Scenario: token usage is emitted with BillingEvent costs when present
- **WHEN** summarisation occurs and a `BillingEvent` with `total_cost=0.007` was in the LLM stream
- **THEN** `_emit_token_usage` is called with `prompt_tokens=0`, `completion_tokens=0`, and `total_cost=0.007`

#### Scenario: token usage is emitted with zero costs when BillingEvent is absent
- **WHEN** summarisation occurs and no `BillingEvent` was in the LLM stream, and `CompletionDoneEvent` reports `prompt_tokens=12, completion_tokens=6`
- **THEN** `_emit_token_usage` is called with `prompt_tokens=12`, `completion_tokens=6`, and all cost arguments equal to `0.0`
