## Why

Each `MessageContextStrategy` subclass currently maintains two coupled hooks:
`_apply_strategy()` mutates `self._records` (and, for `SummaryStrategy`, calls
the LLM) eagerly after every message append, while `_get_context()` lazily
projects the LLM-facing view at read time. This duplicates the "compute the
view" intent across two methods, makes the append path unexpectedly heavy
(it can fire an LLM round-trip), and makes the SlidingWindow trim redundant
with the slice that `_get_context()` already does. Folding the apply logic
into `_get_context()` leaves a single hook per subclass and turns appends
back into pure record accumulation.

## What Changes

- **BREAKING**: Remove the abstract `MessageContextStrategy._apply_strategy()`
  method. `add_user_query()` and `add_model_response()` no longer await it —
  they only append the new `MessageRecord` and return.
- **BREAKING**: `MessageContextStrategy._get_context()` becomes `async`. The
  base `get_context()` becomes `async` and `await`s `_get_context()`. Every
  caller of `get_context()` must `await` it.
- Remove `DummyStrategy._apply_strategy()` (was a no-op). `_get_context()`
  is unchanged in body, only its signature becomes `async`.
- Move `SlidingWindowStrategy._apply_strategy()` body into
  `_get_context()`. Because `_get_context()` already returned the last
  `window_size` records, the only observable change is that `self._records`
  is no longer trimmed on append — it accumulates. `get_history()` therefore
  exposes the full untrimmed record list.
- Move `SummaryStrategy._apply_strategy()` body into `_get_context()`.
  Summarisation (the `self._llm.acompletion(...)` round-trip plus
  `_summary` rotation) now happens lazily inside `_get_context()` whenever
  the post-anchor record count reaches `window_size`. Records continue to be
  preserved across summarisation.
- Remove the `SlidingWindowStrategy.create()` and `SummaryStrategy.create()`
  classmethods — they only existed to await `_apply_strategy()` after
  construction, which no longer exists. Callers construct via the regular
  `__init__`.
- `MessageContextStrategyFactory.build()` becomes synchronous (no awaits to
  perform). Its callers (`Session.create`, `Session.set_message_context_strategy`)
  drop the `await`.
- `Session.acompletion()` awaits the now-async `get_context()`.

## Capabilities

### New Capabilities

(none — refactor of existing behaviour)

### Modified Capabilities

- `message-context-strategy`: removal of `_apply_strategy` from the abstract
  contract and from every concrete subclass; `_get_context` becomes async
  and absorbs the apply behaviour for SlidingWindow and Summary; `create()`
  classmethods removed; factory becomes synchronous; SlidingWindow no longer
  trims `_records`.
- `session`: `acompletion` awaits `get_context()`; `set_message_context_strategy`
  and `create` no longer await `factory.build()`.

## Impact

- Affected code:
  - `server/application/domain/model/context_strategy/base.py` — drop abstract
    `_apply_strategy`; make `_get_context` and `get_context` async; stop calling
    `_apply_strategy` from `add_user_query`/`add_model_response`.
  - `server/application/domain/model/context_strategy/dummy_strategy.py` — drop
    `_apply_strategy`; mark `_get_context` async.
  - `server/application/domain/model/context_strategy/sliding_window_strategy.py`
    — drop `_apply_strategy` and `create()`; mark `_get_context` async.
  - `server/application/domain/model/context_strategy/summary_strategy.py` —
    drop `_apply_strategy` and `create()`; move summarisation into async
    `_get_context`.
  - `server/application/domain/model/context_strategy/factory.py` — make
    `build()` synchronous; instantiate strategies via constructors.
  - `server/application/domain/model/session.py` — `await` `get_context()` in
    `acompletion`; remove `await` from `factory.build()` calls in `create()`
    and `set_message_context_strategy()`.
  - Tests in `tests/domain/entities/test_context_strategy.py` and any
    session tests that call `factory.build()` or `_apply_strategy()`.
- Behaviour shift (semantics, not data):
  - `SummaryStrategy` summarisation now triggers on `get_context()` rather
    than on the preceding `add_*` call. End-to-end Session behaviour is
    preserved because `Session.acompletion` calls `get_context()` after the
    user-prompt append and before the LLM request.
  - `SlidingWindowStrategy` keeps the entire record history in
    `self._records`. `get_history()` (persistence shape) now returns the
    full unwindowed list; the windowed view is still produced by
    `get_context()`. Persistence file size for sliding-window sessions will
    grow accordingly.
- No external API contract changes beyond the `await` site for
  `get_context()` and the dropped `await` on `factory.build()`.
