## ADDED Requirements

### Requirement: MessageRecord value object
A `MessageRecord` is an immutable value object representing a single turn in the conversation. It SHALL carry a UUID `id`, an optional `prev_id` pointing to the preceding record (or `None` for the first record), and a `message` dict with at minimum a `"role"` key and a `"content"` key. The `prev_id` chain forms a singly-linked list that encodes insertion order independently of list position, enabling order reconstruction after trimming.

#### Scenario: First record has no predecessor
- **WHEN** the first message is added to an empty strategy
- **THEN** the resulting `MessageRecord` has `prev_id = None`

#### Scenario: Subsequent records link to their predecessor
- **WHEN** a second message is added after the first
- **THEN** the second `MessageRecord.prev_id` equals the first `MessageRecord.id`

#### Scenario: MessageRecord is a NamedTuple
- **WHEN** a `MessageRecord` is created
- **THEN** it is an instance of `tuple` and its fields are accessible by name

---

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

#### Scenario: token usage handler is called on summarisation
- **WHEN** a `TokenUsageHandler` is registered via `OnTokenUsage()` and a token-producing LLM call occurs inside `_apply_strategy()`
- **THEN** the handler receives `(provider, model, prompt_tokens, completion_tokens)` matching the LLM response

---

### Requirement: DummyStrategy — pass-through history
`DummyStrategy` SHALL retain all records without any pruning. Its `strategy_type` SHALL be the string `"dummy"`. Its `get_metadata()` SHALL return an empty dict. It is the default strategy returned by `MessageContextStrategyFactory.default()`.

#### Scenario: get_history returns all records in order
- **WHEN** multiple messages have been added
- **THEN** `get_history()` includes all of them in insertion order (after any system prompt)

#### Scenario: _apply_strategy is a no-op
- **WHEN** any number of messages are added
- **THEN** no records are removed and no LLM calls are made

#### Scenario: get_metadata returns empty dict
- **WHEN** `get_metadata()` is called on DummyStrategy
- **THEN** the result is `{}`

---

### Requirement: SlidingWindowStrategy — fixed-size recent history
`SlidingWindowStrategy` SHALL keep only the most-recent N records, where N is the `window_size` parameter (minimum 1). After every message addition `_apply_strategy()` MUST trim `_records` to the last `window_size` entries if the count exceeds the window. Its `strategy_type` SHALL be `"sliding_window"`. Its `get_metadata()` SHALL return `{"window_size": <int>}`. A `window_size` of 0 or less SHALL raise `ValueError`.

#### Scenario: window_size zero raises ValueError
- **WHEN** `SlidingWindowStrategy` is instantiated with `window_size=0`
- **THEN** a `ValueError` is raised with a message containing "window_size must be >= 1"

#### Scenario: records within window are not trimmed
- **WHEN** the number of records is less than or equal to `window_size`
- **THEN** all records are retained unchanged

#### Scenario: oldest records are dropped when window is exceeded
- **WHEN** the number of records exceeds `window_size`
- **THEN** only the most-recent `window_size` records are retained, in their original order

#### Scenario: create() applies strategy to pre-existing records
- **WHEN** `SlidingWindowStrategy.create()` is called with a `records` list that already exceeds the window
- **THEN** the returned instance's record list is already trimmed to `window_size`

---

### Requirement: SummaryStrategy — LLM-based rolling summary
`SummaryStrategy` SHALL maintain a rolling text summary of older conversation turns produced by the LLM itself. When the record count exceeds `window_size`, `_apply_strategy()` MUST call the LLM with the full message history (including system prompt and all current records) and store the LLM's response as the new `_summary`, then clear `_records` to an empty list. Its `strategy_type` SHALL be `"summary"`. Its `get_metadata()` SHALL return `{"window_size": <int>, "summary": <str>}`. A `window_size` of 0 or less SHALL raise `ValueError`. A `None` LLM port SHALL raise `ValueError`.

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

#### Scenario: token usage is emitted after summarisation
- **WHEN** summarisation occurs (LLM is called)
- **THEN** any registered `TokenUsageHandler` is invoked with the provider, model, and token counts from the summarisation call

---

### Requirement: MessageContextStrategyFactory — build and restore strategies
`MessageContextStrategyFactory` provides two static methods. `build(strategy_type, metadata, records, llm, completion_config)` SHALL reconstruct a strategy from its serialised state. `default(llm, completion_config)` SHALL return a `DummyStrategy` with no records. Passing an unknown `strategy_type` to `build()` SHALL raise `ValueError`.

#### Scenario: build with type "dummy" returns DummyStrategy
- **WHEN** `build("dummy", {}, [], llm, config)` is called
- **THEN** a `DummyStrategy` instance is returned

#### Scenario: build with type "sliding_window" returns SlidingWindowStrategy with default window 8
- **WHEN** `build("sliding_window", {}, [], llm, config)` is called with no `window_size` in metadata
- **THEN** a `SlidingWindowStrategy` instance is returned with `window_size=8`

#### Scenario: build with type "sliding_window" honours metadata window_size
- **WHEN** `build("sliding_window", {"window_size": 5}, [], llm, config)` is called
- **THEN** the returned strategy has `window_size=5`

#### Scenario: build with type "summary" returns SummaryStrategy with default window 4
- **WHEN** `build("summary", {"summary": ""}, [], llm, config)` is called with no `window_size` in metadata
- **THEN** a `SummaryStrategy` instance is returned with `window_size=4`

#### Scenario: build with type "summary" restores prior summary text
- **WHEN** `build("summary", {"window_size": 3, "summary": "prior"}, [], llm, config)` is called
- **THEN** the returned strategy's metadata contains `summary="prior"`

#### Scenario: build with unknown type raises ValueError
- **WHEN** `build("nonexistent", {}, [], llm, config)` is called
- **THEN** a `ValueError` is raised with a message containing "Unknown strategy type"

#### Scenario: default returns DummyStrategy
- **WHEN** `MessageContextStrategyFactory.default(llm, config)` is called
- **THEN** a `DummyStrategy` instance with no records is returned
