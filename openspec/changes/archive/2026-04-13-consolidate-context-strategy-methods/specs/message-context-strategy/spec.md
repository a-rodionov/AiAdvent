## MODIFIED Requirements

### Requirement: MessageContextStrategy abstract interface

`MessageContextStrategy` is an abstract base class that defines the contract for all conversation-history management strategies. The constructor SHALL accept `llm` (an object satisfying `ILlmPort` Protocol), `completion_config` (CompletionConfig), and optional `records` (list of MessageRecord). It SHALL NOT have any token usage handler mechanism — no `OnTokenUsage`, no `_emit_token_usage`, no `_token_usage_handlers`. Token usage tracking is handled externally by `LlmStatsDecorator`.

The base class SHALL define:

- `add_user_query(content)` — async; appends a new `MessageRecord` with `role="user"` and the given content to `self._records`. It SHALL NOT perform any other work — no trimming, no LLM calls, no strategy application.
- `add_model_response(content)` — async; appends a new `MessageRecord` with `role="assistant"` and the given content to `self._records`. It SHALL NOT perform any other work.
- `get_history()` — a concrete, non-overridden synchronous method returning `list(self._records)` (a shallow copy of the `MessageRecord` list). It is the persistence-facing view of the strategy; subclasses MUST NOT override it.
- `get_context()` — a concrete async method returning the ordered message dicts to send to the LLM on the next turn. When `CompletionConfig.system_prompt` is non-empty, the first element of the returned list is `{"role": "system", "content": <system_prompt>}`, followed by the strategy's per-turn view produced by `await self._get_context()`. Subclasses MAY override the abstract `_get_context()` (which is async) to change the per-turn view; overriding `get_context()` itself is reserved for the base class.

Concrete subclasses SHALL implement `strategy_type` (str property), `get_metadata()` (returns a JSON-serialisable dict of strategy state), and async `_get_context()` (returns the ordered message dicts to include in the next LLM call, without the system prompt). Subclasses SHALL NOT define an `_apply_strategy()` method — the abstract method does not exist and is not called by the base class.

The base class SHALL NOT expose a `get_records()` method or any other method returning `MessageRecord`s outside of `get_history()`. The base class SHALL NOT declare or call any `_apply_strategy()` method.

#### Scenario: add_user_query appends a user-role record

- **WHEN** `add_user_query(content)` is called
- **THEN** a new `MessageRecord` with `role="user"` and the given content is appended to the record list, and no other side effects occur (no trimming, no LLM calls)

#### Scenario: add_model_response appends an assistant-role record

- **WHEN** `add_model_response(content)` is called
- **THEN** a new `MessageRecord` with `role="assistant"` and the given content is appended to the record list, and no other side effects occur (no trimming, no LLM calls)

#### Scenario: add_user_query does not call _apply_strategy

- **WHEN** a developer inspects `MessageContextStrategy.add_user_query`
- **THEN** there is no call to `_apply_strategy` and no `await` of any strategy-application hook

#### Scenario: add_model_response does not call _apply_strategy

- **WHEN** a developer inspects `MessageContextStrategy.add_model_response`
- **THEN** there is no call to `_apply_strategy` and no `await` of any strategy-application hook

#### Scenario: get_history returns the raw MessageRecord list

- **WHEN** `get_history()` is called after three messages have been appended
- **THEN** the return value is a `list[MessageRecord]` of length three, in insertion order, containing the same `MessageRecord` objects that were appended

#### Scenario: get_history returns a shallow copy

- **WHEN** `get_history()` is called twice
- **THEN** each call returns a new list object; mutating one does not affect `self._records`

#### Scenario: get_context is awaitable

- **WHEN** a developer inspects `MessageContextStrategy.get_context`
- **THEN** the method is declared `async` and returns `list[dict[str, str]]` when awaited

#### Scenario: get_context prepends system prompt when configured

- **WHEN** `CompletionConfig.system_prompt` is non-empty
- **THEN** `await get_context()` returns a list whose first element is `{"role": "system", "content": <system_prompt>}`, followed by the elements returned by `await _get_context()`

#### Scenario: get_context omits system prompt when not configured

- **WHEN** `CompletionConfig.system_prompt` is an empty string
- **THEN** `await get_context()` returns exactly the elements returned by `await _get_context()`

#### Scenario: _apply_strategy method does not exist

- **WHEN** a developer inspects `MessageContextStrategy` or any subclass
- **THEN** there is no `_apply_strategy` attribute, no abstract declaration of `_apply_strategy`, and the base class never calls a method by that name

#### Scenario: get_records method does not exist

- **WHEN** a developer inspects `MessageContextStrategy`
- **THEN** there is no `get_records` method on the base class or any subclass; persistence callers use `get_history()` instead

#### Scenario: no token usage handler mechanism exists

- **WHEN** a developer inspects `MessageContextStrategy`
- **THEN** there is no `OnTokenUsage` method, no `_emit_token_usage` method, no `_token_usage_handlers` member, and no `TokenUsageHandler` type alias

---

### Requirement: DummyStrategy — pass-through history

`DummyStrategy` SHALL retain all records without any pruning. Its `strategy_type` SHALL be the string `"dummy"`. Its `get_metadata()` SHALL return an empty dict. `DummyStrategy` SHALL inherit the base `get_context()` implementation and provide an async `_get_context()` returning `[record.message for record in self._records]`. `DummyStrategy` SHALL NOT define an `_apply_strategy()` method. `DummyStrategy` SHALL live in its own module `server/application/domain/model/context_strategy/dummy_strategy.py`.

#### Scenario: get_context returns all records in insertion order

- **WHEN** multiple messages have been added
- **THEN** `await get_context()` includes all of them in insertion order (after any system prompt)

#### Scenario: appending messages does not invoke any LLM call

- **WHEN** any number of messages are added via `add_user_query` / `add_model_response`
- **THEN** no records are removed and no LLM calls are made; `_records` simply grows

#### Scenario: _apply_strategy method does not exist on DummyStrategy

- **WHEN** a developer inspects `DummyStrategy`
- **THEN** the class has no `_apply_strategy` attribute

#### Scenario: get_metadata returns empty dict

- **WHEN** `get_metadata()` is called on DummyStrategy
- **THEN** the result is `{}`

#### Scenario: DummyStrategy is importable from the package root

- **WHEN** a caller imports `DummyStrategy` from `server.application.domain.model.context_strategy`
- **THEN** the import resolves to the class defined in `dummy_strategy.py`

---

### Requirement: SlidingWindowStrategy — fixed-size recent history

`SlidingWindowStrategy` SHALL keep all appended records in `self._records` without trimming and SHALL project the last N records on demand, where N is the `window_size` parameter (minimum 1). Its `strategy_type` SHALL be `"sliding_window"`. Its `get_metadata()` SHALL return `{"window_size": <int>}`. A `window_size` of 0 or less SHALL raise `ValueError` from the constructor. `SlidingWindowStrategy` SHALL provide an async `_get_context()` that returns the message dicts of the last `window_size` entries of `self._records`. `SlidingWindowStrategy` SHALL NOT define an `_apply_strategy()` method and SHALL NOT define a `create()` classmethod — the constructor is the only construction path. `SlidingWindowStrategy` SHALL live in its own module `server/application/domain/model/context_strategy/sliding_window_strategy.py`.

#### Scenario: window_size zero raises ValueError

- **WHEN** `SlidingWindowStrategy` is instantiated with `window_size=0`
- **THEN** a `ValueError` is raised with a message containing "window_size must be >= 1"

#### Scenario: records are never trimmed by add operations

- **WHEN** more records than `window_size` are appended via `add_user_query` / `add_model_response`
- **THEN** every appended record remains in `self._records`; `get_history()` returns all of them in insertion order

#### Scenario: get_history exposes the full untrimmed record list

- **WHEN** `get_history()` is called after 10 messages have been added with `window_size=3`
- **THEN** the returned list has length 10, in insertion order

#### Scenario: get_context returns the last window_size records

- **WHEN** `await get_context()` is called with `window_size=3` and five records present
- **THEN** the returned list (after the optional system prompt) contains exactly the message dicts of the last three records in insertion order

#### Scenario: _apply_strategy method does not exist on SlidingWindowStrategy

- **WHEN** a developer inspects `SlidingWindowStrategy`
- **THEN** the class has no `_apply_strategy` attribute

#### Scenario: create classmethod does not exist on SlidingWindowStrategy

- **WHEN** a developer inspects `SlidingWindowStrategy`
- **THEN** the class has no `create` classmethod; instances are constructed via `SlidingWindowStrategy(window_size=..., llm=..., completion_config=..., records=...)`

#### Scenario: SlidingWindowStrategy is importable from the package root

- **WHEN** a caller imports `SlidingWindowStrategy` from `server.application.domain.model.context_strategy`
- **THEN** the import resolves to the class defined in `sliding_window_strategy.py`

---

### Requirement: SummaryStrategy — LLM-based rolling summary

`SummaryStrategy` SHALL maintain a rolling text summary of older conversation turns produced by the LLM itself, anchored to a specific `MessageRecord.id`. The strategy's `_summary` attribute SHALL hold a `Summary` value object with two fields: `text` (str — the summary produced by the LLM; empty string before any summarisation has occurred) and `anchor_id` (`UUID | None` — the id of the `MessageRecord` for which the current summary was produced; `None` before any summarisation has occurred). `SummaryStrategy` SHALL live in its own module `server/application/domain/model/context_strategy/summary_strategy.py`, which SHALL also define the `Summary` value object. `SummaryStrategy` SHALL NOT define an `_apply_strategy()` method and SHALL NOT define a `create()` classmethod.

`_get_context()` SHALL be `async` and SHALL perform both the lazy summarisation check and the projection of the LLM-facing message list. The summarisation check SHALL: count `MessageRecord`s in `self._records` after the record identified by `_summary.anchor_id` (when `_summary.anchor_id` is `None`, the count is measured from the start of `self._records`); when this count is greater than or equal to `window_size`, perform the summarisation step; otherwise skip the summarisation step.

The summarisation step SHALL call `self._llm.acompletion` with a message list built from: (a) the system prompt from `CompletionConfig` when configured, (b) `[{"role": "user", "content": self._summary.text}]` when `self._summary.text` is non-empty, followed by (c) the message dicts of records appended after `_summary.anchor_id`. The returned assistant text SHALL replace `self._summary.text` and `self._summary.anchor_id` SHALL be set to the id of the most recent `MessageRecord` in `self._records` at the time of summarisation. `self._records` SHALL NOT be cleared.

After the (optional) summarisation step, `_get_context()` SHALL return: when `_summary.anchor_id is None`, the message dicts of every record in `self._records`; otherwise `[{"role": "user", "content": self._summary.text}]` followed by the message dicts of the records appended after the (possibly just-updated) `_summary.anchor_id`.

`strategy_type` SHALL be `"summary"`. `get_metadata()` SHALL return `{"window_size": <int>, "summary_text": <str>, "summary_anchor_id": <str | None>, "summarization_prompt": <str>}`, where `summary_anchor_id` is the string form of the anchor UUID or `None`. Backwards compatibility with the prior plain-string `summary` metadata is NOT required.

#### Scenario: window_size zero raises ValueError

- **WHEN** `SummaryStrategy` is instantiated with `window_size=0`
- **THEN** a `ValueError` is raised with a message containing "window_size must be >= 1"

#### Scenario: None LLM raises ValueError

- **WHEN** `SummaryStrategy` is instantiated with `llm=None`
- **THEN** a `ValueError` is raised with a message containing "LlmAdapter object is None"

#### Scenario: appending messages alone does not trigger summarisation

- **WHEN** records are appended via `add_user_query` / `add_model_response` and `get_context()` is never called
- **THEN** `self._llm.acompletion` is not called and `_summary` remains unchanged regardless of how many records have been appended

#### Scenario: anchor None and fewer than window_size records do not trigger on get_context

- **WHEN** `_summary.anchor_id is None`, `len(self._records)` is less than `window_size`, and `await get_context()` is called
- **THEN** `self._llm.acompletion` is not called and `_summary` remains unchanged

#### Scenario: anchor None and window_size records trigger first summarisation on get_context

- **WHEN** `_summary.anchor_id is None`, `len(self._records)` is greater than or equal to `window_size`, and `await get_context()` is called
- **THEN** `self._llm.acompletion` is called once; on completion `_summary.text` is set to the LLM response and `_summary.anchor_id` is set to the id of the most recent record in `self._records`

#### Scenario: fewer than window_size records after anchor do not retrigger

- **WHEN** `_summary.anchor_id` is a UUID `U`, fewer than `window_size` records have been appended after `U`, and `await get_context()` is called
- **THEN** `self._llm.acompletion` is not called and `_summary` remains unchanged

#### Scenario: window_size records after anchor retrigger summarisation on get_context

- **WHEN** `_summary.anchor_id` is a UUID `U`, `window_size` or more records have been appended after `U`, and `await get_context()` is called
- **THEN** `self._llm.acompletion` is called with `[{"role":"user","content": previous_summary_text}]` followed by the records after `U` (plus system prompt when configured); `_summary.text` is replaced with the LLM response, and `_summary.anchor_id` is updated to the id of the most recent record

#### Scenario: records are preserved across summarisation

- **WHEN** `await get_context()` triggers summarisation
- **THEN** `self._records` retains every record it held before the call; no record is removed

#### Scenario: get_context with no anchor returns all records

- **WHEN** `_summary.anchor_id is None` and the record count is below `window_size` (no summarisation fires)
- **THEN** `await get_context()` returns the message dicts of every record in `self._records` (after the optional system prompt)

#### Scenario: get_context with anchor prepends summary and slices records after anchor

- **WHEN** `_summary.anchor_id` is a UUID `U`, records after `U` are `R1, R2`, and the post-anchor count is below `window_size` (no new summarisation fires)
- **THEN** `await get_context()` returns `[{"role":"user","content": self._summary.text}, R1.message, R2.message]` (after the optional system prompt)

#### Scenario: get_metadata carries anchor id as string

- **WHEN** `get_metadata()` is called after a `await get_context()` produced anchor UUID `U`
- **THEN** the returned dict has `summary_anchor_id` equal to `str(U)` and `summary_text` equal to the summary text

#### Scenario: _apply_strategy method does not exist on SummaryStrategy

- **WHEN** a developer inspects `SummaryStrategy`
- **THEN** the class has no `_apply_strategy` attribute

#### Scenario: create classmethod does not exist on SummaryStrategy

- **WHEN** a developer inspects `SummaryStrategy`
- **THEN** the class has no `create` classmethod; instances are constructed via the regular constructor

#### Scenario: token usage is tracked by decorator transparently

- **WHEN** `await get_context()` triggers summarisation and `self._llm` is a `LlmStatsDecorator`
- **THEN** the decorator intercepts `CompletionDoneEvent` and accumulates stats into `SessionUsageStats` without any explicit call in the strategy

#### Scenario: no _emit_token_usage call in _get_context

- **WHEN** a developer inspects `SummaryStrategy._get_context`
- **THEN** there is no call to `_emit_token_usage` — the decorator handles stats accumulation

#### Scenario: SummaryStrategy is importable from the package root

- **WHEN** a caller imports `SummaryStrategy` from `server.application.domain.model.context_strategy`
- **THEN** the import resolves to the class defined in `summary_strategy.py`

---

### Requirement: MessageContextStrategyFactory — build and restore strategies

`MessageContextStrategyFactory.build(strategy_type, metadata, records, llm, completion_config)` SHALL be a synchronous static method that reconstructs a strategy from its serialised state by invoking the concrete subclass constructor directly. The `llm` parameter is an `ILlmPort`-compatible object (which will be a `LlmStatsDecorator` when called from Session). The `default()` static method is REMOVED — the concept of a default strategy is now configuration-driven via `MessageContextStrategyDefaults` and the `default_message_context_strategy` server config parameter, not hardcoded in the factory. The factory SHALL live in `server/application/domain/model/context_strategy/factory.py` and import each concrete strategy class from its sibling module. The factory SHALL NOT call any `create()` classmethod on the strategy classes (none exists) and SHALL NOT `await` anything inside `build()`.

For `strategy_type == "summary"`, the factory SHALL read `window_size` (default `4`), `summary_text` (default `""`), `summary_anchor_id` (default `None`; when present it is parsed as a UUID), and `summarization_prompt` (default `""`) from `metadata`, and build a `SummaryStrategy` whose `_summary` is `Summary(text=summary_text, anchor_id=parsed_anchor_id)`.

#### Scenario: build is synchronous

- **WHEN** a developer inspects `MessageContextStrategyFactory.build`
- **THEN** the method is not declared `async` and returns a `MessageContextStrategy` directly (not a coroutine)

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

#### Scenario: build does not invoke any create classmethod

- **WHEN** a developer inspects `MessageContextStrategyFactory.build`
- **THEN** there is no call to `SlidingWindowStrategy.create` or `SummaryStrategy.create` — instances are produced by direct constructor calls

#### Scenario: default() method does not exist

- **WHEN** a developer inspects `MessageContextStrategyFactory`
- **THEN** there is no `default` method — default strategy selection is handled by configuration

#### Scenario: factory is importable from the package root

- **WHEN** a caller imports `MessageContextStrategyFactory` from `server.application.domain.model.context_strategy`
- **THEN** the import resolves to the class defined in `factory.py`
