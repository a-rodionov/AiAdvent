## MODIFIED Requirements

### Requirement: MessageContextStrategy abstract interface

`MessageContextStrategy` is an abstract base class that defines the contract for all conversation-history management strategies. The constructor SHALL accept `llm` (an object satisfying `ILlmPort` Protocol), `completion_config` (CompletionConfig), and optional `records` (list of MessageRecord). It SHALL NOT have any token usage handler mechanism — no `OnTokenUsage`, no `_emit_token_usage`, no `_token_usage_handlers`. Token usage tracking is handled externally by `LlmStatsDecorator`.

The base class SHALL define:

- `get_history()` — a concrete, non-overridden method returning `list(self._records)` (a shallow copy of the `MessageRecord` list). It is the persistence-facing view of the strategy; subclasses MUST NOT override it.
- `get_context()` — a concrete method returning the ordered message dicts to send to the LLM on the next turn. When `CompletionConfig.system_prompt` is non-empty, the first element of the returned list is `{"role": "system", "content": <system_prompt>}`, followed by the strategy's per-turn view produced by `_get_context()`. Subclasses MAY override `_get_context()` to change the per-turn view; overriding `get_context()` itself is reserved for the base class.

Concrete subclasses SHALL implement `strategy_type` (str property), `get_metadata()` (returns a JSON-serialisable dict of strategy state), `_apply_strategy()` (async, called after every message addition), and `_get_context()` (returns the ordered message dicts to include in the next LLM call, without the system prompt).

The base class SHALL NOT expose a `get_records()` method or any other method returning `MessageRecord`s outside of `get_history()`.

#### Scenario: add_user_query appends a user-role record

- **WHEN** `add_user_query(content)` is called
- **THEN** a new `MessageRecord` with `role="user"` and the given content is appended to the record list, and `_apply_strategy()` is awaited

#### Scenario: add_model_response appends an assistant-role record

- **WHEN** `add_model_response(content)` is called
- **THEN** a new `MessageRecord` with `role="assistant"` and the given content is appended to the record list, and `_apply_strategy()` is awaited

#### Scenario: get_history returns the raw MessageRecord list

- **WHEN** `get_history()` is called after three messages have been appended
- **THEN** the return value is a `list[MessageRecord]` of length three, in insertion order, containing the same `MessageRecord` objects that were appended

#### Scenario: get_history returns a shallow copy

- **WHEN** `get_history()` is called twice
- **THEN** each call returns a new list object; mutating one does not affect `self._records`

#### Scenario: get_context prepends system prompt when configured

- **WHEN** `CompletionConfig.system_prompt` is non-empty
- **THEN** `get_context()` returns a list whose first element is `{"role": "system", "content": <system_prompt>}`, followed by the elements returned by `_get_context()`

#### Scenario: get_context omits system prompt when not configured

- **WHEN** `CompletionConfig.system_prompt` is an empty string
- **THEN** `get_context()` returns exactly the elements returned by `_get_context()`

#### Scenario: get_records method does not exist

- **WHEN** a developer inspects `MessageContextStrategy`
- **THEN** there is no `get_records` method on the base class or any subclass; persistence callers use `get_history()` instead

#### Scenario: no token usage handler mechanism exists

- **WHEN** a developer inspects `MessageContextStrategy`
- **THEN** there is no `OnTokenUsage` method, no `_emit_token_usage` method, no `_token_usage_handlers` member, and no `TokenUsageHandler` type alias

---

### Requirement: DummyStrategy — pass-through history

`DummyStrategy` SHALL retain all records without any pruning. Its `strategy_type` SHALL be the string `"dummy"`. Its `get_metadata()` SHALL return an empty dict. `DummyStrategy` SHALL inherit the base `get_context()` implementation and provide `_get_context()` returning `[record.message for record in self._records]`. `DummyStrategy` SHALL live in its own module `server/application/domain/model/context_strategy/dummy_strategy.py`.

#### Scenario: get_context returns all records in insertion order

- **WHEN** multiple messages have been added
- **THEN** `get_context()` includes all of them in insertion order (after any system prompt)

#### Scenario: \_apply_strategy is a no-op

- **WHEN** any number of messages are added
- **THEN** no records are removed and no LLM calls are made

#### Scenario: get_metadata returns empty dict

- **WHEN** `get_metadata()` is called on DummyStrategy
- **THEN** the result is `{}`

#### Scenario: DummyStrategy is importable from the package root

- **WHEN** a caller imports `DummyStrategy` from `server.application.domain.model.context_strategy`
- **THEN** the import resolves to the class defined in `dummy_strategy.py`

---

### Requirement: SlidingWindowStrategy — fixed-size recent history

`SlidingWindowStrategy` SHALL keep only the most-recent N records, where N is the `window_size` parameter (minimum 1). After every message addition `_apply_strategy()` MUST trim `_records` to the last `window_size` entries if the count exceeds the window. Its `strategy_type` SHALL be `"sliding_window"`. Its `get_metadata()` SHALL return `{"window_size": <int>}`. A `window_size` of 0 or less SHALL raise `ValueError`. `SlidingWindowStrategy` SHALL override `_get_context()` to return the message dicts of the last `window_size` entries of `self._records`. `SlidingWindowStrategy` SHALL live in its own module `server/application/domain/model/context_strategy/sliding_window_strategy.py`.

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

#### Scenario: get_context returns the last window_size records

- **WHEN** `get_context()` is called with `window_size=3` and five records present
- **THEN** the returned list (after the optional system prompt) contains exactly the message dicts of the last three records in insertion order

#### Scenario: SlidingWindowStrategy is importable from the package root

- **WHEN** a caller imports `SlidingWindowStrategy` from `server.application.domain.model.context_strategy`
- **THEN** the import resolves to the class defined in `sliding_window_strategy.py`

---

### Requirement: SummaryStrategy — LLM-based rolling summary

`SummaryStrategy` SHALL maintain a rolling text summary of older conversation turns produced by the LLM itself, anchored to a specific `MessageRecord.id`. The strategy's `_summary` attribute SHALL hold a `Summary` value object with two fields: `text` (str — the summary produced by the LLM; empty string before any summarisation has occurred) and `anchor_id` (`UUID | None` — the id of the `MessageRecord` for which the current summary was produced; `None` before any summarisation has occurred). `SummaryStrategy` SHALL live in its own module `server/application/domain/model/context_strategy/summary_strategy.py`, which SHALL also define the `Summary` value object.

`_apply_strategy()` SHALL run its summarisation logic only when `window_size` or more `MessageRecord`s have been appended to `self._records` after the record identified by `_summary.anchor_id`. When `_summary.anchor_id` is `None`, the count is measured from the start of `self._records`. When the count is strictly less than `window_size`, `_apply_strategy()` SHALL be a no-op.

When the trigger condition is met, `_apply_strategy()` SHALL call `self._llm.acompletion` with a message list built from: (a) `[{"role": "user", "content": self._summary.text}]` when `self._summary.text` is non-empty, followed by (b) the message dicts of records appended after `_summary.anchor_id`. The system prompt from `CompletionConfig` is prepended when configured. The returned assistant text SHALL replace `self._summary.text` and `self._summary.anchor_id` SHALL be set to the id of the most recent `MessageRecord` in `self._records` at the time of summarisation. `self._records` SHALL NOT be cleared.

`_get_context()` SHALL return: when `_summary.anchor_id is None`, the message dicts of every record in `self._records`; otherwise `[{"role": "user", "content": self._summary.text}]` followed by the message dicts of the records appended after `_summary.anchor_id`.

`strategy_type` SHALL be `"summary"`. `get_metadata()` SHALL return `{"window_size": <int>, "summary_text": <str>, "summary_anchor_id": <str | None>, "summarization_prompt": <str>}`, where `summary_anchor_id` is the string form of the anchor UUID or `None`. Backwards compatibility with the prior plain-string `summary` metadata is NOT required.

#### Scenario: window_size zero raises ValueError

- **WHEN** `SummaryStrategy` is instantiated with `window_size=0`
- **THEN** a `ValueError` is raised with a message containing "window_size must be >= 1"

#### Scenario: None LLM raises ValueError

- **WHEN** `SummaryStrategy` is instantiated with `llm=None`
- **THEN** a `ValueError` is raised with a message containing "LlmAdapter object is None"

#### Scenario: anchor None and fewer than window_size records do not trigger

- **WHEN** `_summary.anchor_id is None` and `len(self._records)` is less than `window_size`
- **THEN** `_apply_strategy()` makes no LLM call and leaves `_summary` unchanged

#### Scenario: anchor None and window_size records trigger first summarisation

- **WHEN** `_summary.anchor_id is None` and `len(self._records)` is greater than or equal to `window_size`
- **THEN** `self._llm.acompletion` is called, `_summary.text` is set to the LLM response, and `_summary.anchor_id` is set to the id of the most recent record in `self._records`

#### Scenario: fewer than window_size records after anchor do not retrigger

- **WHEN** `_summary.anchor_id` is a UUID `U` and fewer than `window_size` records have been appended after `U`
- **THEN** `_apply_strategy()` makes no LLM call and leaves `_summary` unchanged

#### Scenario: window_size records after anchor retrigger summarisation

- **WHEN** `_summary.anchor_id` is a UUID `U` and `window_size` or more records have been appended after `U`
- **THEN** `self._llm.acompletion` is called with `[{"role":"user","content": previous_summary_text}]` followed by the records after `U` (plus system prompt when configured), `_summary.text` is replaced with the LLM response, and `_summary.anchor_id` is updated to the id of the most recent record

#### Scenario: records are preserved across summarisation

- **WHEN** `_apply_strategy()` summarises
- **THEN** `self._records` retains every record it held before the call; no record is removed

#### Scenario: get_context with no anchor returns all records

- **WHEN** `_summary.anchor_id is None`
- **THEN** `_get_context()` returns `[record.message for record in self._records]`

#### Scenario: get_context with anchor prepends summary and slices records after anchor

- **WHEN** `_summary.anchor_id` is a UUID `U` and records after `U` are `R1, R2`
- **THEN** `_get_context()` returns `[{"role":"user","content": self._summary.text}, R1.message, R2.message]`

#### Scenario: get_metadata carries anchor id as string

- **WHEN** `get_metadata()` is called after summarisation produced anchor UUID `U`
- **THEN** the returned dict has `summary_anchor_id` equal to `str(U)` and `summary_text` equal to the summary text

#### Scenario: token usage is tracked by decorator transparently

- **WHEN** summarisation occurs and `self._llm` is a `LlmStatsDecorator`
- **THEN** the decorator intercepts `CompletionDoneEvent` and accumulates stats into `SessionUsageStats` without any explicit call in the strategy

#### Scenario: no _emit_token_usage call in _apply_strategy

- **WHEN** a developer inspects `SummaryStrategy._apply_strategy`
- **THEN** there is no call to `_emit_token_usage` — the decorator handles stats accumulation

#### Scenario: SummaryStrategy is importable from the package root

- **WHEN** a caller imports `SummaryStrategy` from `server.application.domain.model.context_strategy`
- **THEN** the import resolves to the class defined in `summary_strategy.py`

---

### Requirement: MessageContextStrategyFactory — build and restore strategies

`MessageContextStrategyFactory.build(strategy_type, metadata, records, llm, completion_config)` SHALL reconstruct a strategy from its serialised state. The `llm` parameter is an `ILlmPort`-compatible object (which will be a `LlmStatsDecorator` when called from Session). The `default()` static method is REMOVED — the concept of a default strategy is now configuration-driven via `MessageContextStrategyDefaults` and the `default_message_context_strategy` server config parameter, not hardcoded in the factory. The factory SHALL live in `server/application/domain/model/context_strategy/factory.py` and import each concrete strategy class from its sibling module.

For `strategy_type == "summary"`, the factory SHALL read `window_size` (default `4`), `summary_text` (default `""`), `summary_anchor_id` (default `None`; when present it is parsed as a UUID), and `summarization_prompt` (default `""`) from `metadata`, and build a `SummaryStrategy` whose `_summary` is `Summary(text=summary_text, anchor_id=parsed_anchor_id)`.

#### Scenario: build with type "dummy" returns DummyStrategy

- **WHEN** `build("dummy", {}, [], llm, config)` is called
- **THEN** a `DummyStrategy` instance is returned

#### Scenario: build with type "sliding_window" returns SlidingWindowStrategy with default window 8

- **WHEN** `build("sliding_window", {}, [], llm, config)` is called with no `window_size` in metadata
- **THEN** a `SlidingWindowStrategy` instance is returned with `window_size=8`

#### Scenario: build with type "sliding_window" honours metadata window_size

- **WHEN** `build("sliding_window", {"window_size": 5}, [], llm, config)` is called
- **THEN** the returned strategy has `window_size=5`

#### Scenario: build with type "summary" returns SummaryStrategy with default window 4 and empty summary

- **WHEN** `build("summary", {}, [], llm, config)` is called with no `window_size` or summary fields in metadata
- **THEN** a `SummaryStrategy` is returned with `window_size=4`, `_summary.text == ""`, and `_summary.anchor_id is None`

#### Scenario: build with type "summary" restores prior summary and anchor

- **WHEN** `build("summary", {"window_size": 3, "summary_text": "prior", "summary_anchor_id": "<uuid-str>", "summarization_prompt": "..."}, [], llm, config)` is called
- **THEN** the returned strategy's `_summary.text` equals `"prior"` and `_summary.anchor_id` equals the parsed `UUID("<uuid-str>")`

#### Scenario: build with unknown type raises ValueError

- **WHEN** `build("nonexistent", {}, [], llm, config)` is called
- **THEN** a `ValueError` is raised with a message containing "Unknown strategy type"

#### Scenario: build passes llm to strategy constructor

- **WHEN** `build("summary", metadata, records, llm_stats_decorator, config)` is called
- **THEN** the created `SummaryStrategy` stores `llm_stats_decorator` as its `_llm`

#### Scenario: default() method does not exist

- **WHEN** a developer inspects `MessageContextStrategyFactory`
- **THEN** there is no `default` method — default strategy selection is handled by configuration

#### Scenario: factory is importable from the package root

- **WHEN** a caller imports `MessageContextStrategyFactory` from `server.application.domain.model.context_strategy`
- **THEN** the import resolves to the class defined in `factory.py`

## ADDED Requirements

### Requirement: Summary value object

The `summary_strategy` module SHALL define a `Summary` value object (a `NamedTuple`) with fields `text: str` and `anchor_id: UUID | None`. `Summary` is immutable; a new instance is constructed every time the summary is updated. `Summary(text="", anchor_id=None)` SHALL be the initial value held by a `SummaryStrategy` that has not yet summarised.

#### Scenario: Summary is a NamedTuple with text and anchor_id fields

- **WHEN** `Summary(text="s", anchor_id=U)` is constructed
- **THEN** the instance is an instance of `tuple`, `summary.text == "s"`, and `summary.anchor_id == U`

#### Scenario: initial Summary has empty text and no anchor

- **WHEN** a new `SummaryStrategy` is constructed without a prior summary
- **THEN** `strategy._summary == Summary(text="", anchor_id=None)`

