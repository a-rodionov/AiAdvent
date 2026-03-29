## Context

`MessageContextStrategy` (domain model under
`server/application/domain/model/context_strategy/`) currently has two
abstract hooks per subclass:

| Hook              | Called by                                | Purpose                                          |
| ----------------- | ---------------------------------------- | ------------------------------------------------ |
| `_apply_strategy` | `add_user_query`, `add_model_response`, `create()` | Mutates `_records` (and may run an LLM call) eagerly |
| `_get_context`    | base `get_context()`                     | Builds the LLM-facing message-dict view at read time |

The eager mutation is paying for behaviour that the lazy projection already
covers:

- `SlidingWindowStrategy._apply_strategy` trims `_records` to
  `window_size`, but `_get_context` already returns
  `[r.message for r in self._records[-self._window_size:]]`. The trim is
  redundant; its only effect is to keep `get_history()` (the
  persistence-shape accessor) windowed too, which is at odds with the
  prior refactor that made `get_history()` the raw record-list view.
- `SummaryStrategy._apply_strategy` performs the LLM round-trip after every
  `add_*` call. The result of that round-trip is only ever consumed via
  `_get_context()` on the next request — there's no other reader.
- `DummyStrategy._apply_strategy` is a no-op kept only to satisfy the
  abstract contract.

`Session.acompletion` always calls `get_context()` after `add_user_query`
and before the LLM request, so collapsing the two hooks into a single
`_get_context()` (which becomes async) preserves end-to-end behaviour for
the only production caller.

## Goals / Non-Goals

**Goals:**

- Single hook per strategy: `_get_context()` (async) is the only place that
  decides what records are sent and that triggers any side-work needed to
  produce them.
- `add_user_query`/`add_model_response` are pure record appenders — no
  hidden LLM calls, no hidden trimming.
- `_records` is the single source of truth for the persistence shape;
  strategies project from it on demand.
- Drop transitively obsolete API surface: `_apply_strategy`,
  `SlidingWindowStrategy.create()`, `SummaryStrategy.create()`, and the
  async-ness of `MessageContextStrategyFactory.build()`.

**Non-Goals:**

- Changing strategy types or adding new strategies.
- Re-introducing eager state pruning under another name.
- Persisted-data migration. Existing session JSON files continue to
  rehydrate identically — only the call shape inside the domain layer
  changes.
- Making `add_user_query` / `add_model_response` synchronous. They stay
  `async` to preserve the existing call shape (`await session-...`); we
  just remove the awaited body inside.

## Decisions

### D1. `_get_context` becomes async; `get_context` becomes async

Summarisation requires `await self._llm.acompletion(...)`. Once that lives
inside `_get_context`, the method must be `async`. The base `get_context()`
wraps it (prepending the system prompt), so it must `await _get_context()`
and is therefore async too. Every caller of `get_context()` becomes an
`await` site.

**Alternative considered**: keep `_get_context` sync and have a separate
async `_prepare()` that summarises, called from `get_context()` before the
sync `_get_context()` projection. Rejected: that re-introduces the two-hook
shape this change is meant to remove.

### D2. SlidingWindow stops trimming `_records`

With `_apply_strategy` gone, the trim site disappears. Three options:

1. Re-implement the trim inside `_get_context` so `_records` stays bounded.
2. Drop the trim entirely; `_records` accumulates, `_get_context` slices.
3. Trim inside `add_user_query` / `add_model_response` (overriding base).

Option (2) is chosen. It matches the established invariant from the prior
refactor — `get_history()` is the raw, untrimmed record list and the
strategies' job is to project a windowed *view*, not to mutate the source
list. Option (1) would be the single point of truth but mixes a side
effect into a "view" method. Option (3) re-creates two hooks under
different names.

**Trade-off**: persisted sliding-window sessions grow without bound. This
matches what already happens for `SummaryStrategy` (which preserves all
records since the prior refactor) and is consistent with the
"history is persistence; context is projection" split.

### D3. SummaryStrategy summarises lazily on `_get_context()`

`_get_context()` checks the post-anchor record count; if it has reached
`window_size`, it runs the LLM round-trip, rotates `_summary` to
`Summary(text=new_text, anchor_id=self._records[-1].id)`, and only then
returns the projected view (summary + records-after-anchor).

For `Session.acompletion`, the call order is:

1. `await strategy.add_user_query(prompt)` — pure append.
2. `full_messages = await strategy.get_context()` — may summarise here.
3. LLM completion.
4. `await strategy.add_model_response(text)` — pure append.

So summarisation now happens *between* the user append and the LLM call,
rather than immediately after each append. The summary that the LLM sees
on a given turn is identical to what it would have seen under the old
ordering — the user's most recent prompt is included in `_records` before
`_get_context()` runs, just as it was before `_apply_strategy()` ran.

**Edge case**: if the model response (step 4) crosses the threshold, the
summarisation does not happen until the next turn's step 2. Under the old
behaviour it happened in step 4. There is no observable difference for
external callers — between turns, no one reads the summary state.

### D4. Drop `create()` classmethods; `factory.build()` becomes sync

`SlidingWindowStrategy.create` and `SummaryStrategy.create` only existed to
`await self._apply_strategy()` after construction. With apply gone, they
add nothing over the constructor. Dropping them lets
`MessageContextStrategyFactory.build()` shed its `async` keyword too —
nothing inside it needs to await — which removes the `await` from
`Session.create` and `Session.set_message_context_strategy`.

`Session.create` is still async (it still does `await datetime.now()` —
actually it does not, but the method is `async` for forward compatibility
and parity with other Session lifecycle methods); only the inner
`factory.build()` call drops its `await`.

### D5. `_apply_strategy` is removed, not deprecated

The proposal explicitly asks to delete the method from all four classes
(base + three concrete). No deprecation shim is provided. Any external
code calling `_apply_strategy` (a private hook) will break loudly with
`AttributeError`. This is acceptable because `_apply_strategy` is leading
underscore — it is never part of the supported surface.

### D6. Tests that called `_apply_strategy()` directly are rewritten

Several tests in `tests/domain/entities/test_context_strategy.py` invoke
`await s._apply_strategy()` to verify the trigger condition without going
through `add_*`. These are rewritten to call `await s.get_context()`
instead, which is now the canonical trigger site.

## Risks / Trade-offs

- **[Risk]** `Session.acompletion`'s only `get_context()` call site already
  awaits inside the same async generator, so the await addition is
  trivial. Other callers (e.g. tests, future use cases) must remember to
  await. → **Mitigation**: mypy will flag missing awaits because
  `get_context` returns `Coroutine[..., list[dict]]` after the change.

- **[Risk]** `SlidingWindowStrategy.get_history()` now returns the full
  unbounded record list. Any caller that assumed the windowed list (none
  exist in the repo today; the prior refactor already documented
  `get_history()` as the raw view) would receive more records than
  before. → **Mitigation**: spec the new behaviour explicitly; audit call
  sites in `tests/`, adapters, use cases.

- **[Risk]** Lazy summarisation means a `get_context()` call can take as
  long as an LLM round-trip. Today the same wait happens inside
  `add_*`. The total wall-clock for `Session.acompletion` is unchanged.
  → **Mitigation**: document the timing shift in the design and the
  Session spec scenarios; no production code path observes the
  intermediate state.

- **[Trade-off]** `_records` grows without bound for sliding-window
  sessions persisted on disk. Files get larger over the lifetime of a
  session. → Accepted; matches the `SummaryStrategy` invariant established
  by the prior refactor.

- **[Trade-off]** Multiple sequential `get_context()` calls on a
  Summary strategy that has just crossed the threshold will all attempt
  summarisation only on the first call — once the anchor advances, the
  post-anchor count drops to 0 and no further LLM call fires until the
  threshold is crossed again. No additional locking is needed because
  Session is single-task per `acompletion` call.

## Migration Plan

This is a single-commit refactor; no staged rollout needed:

1. Update `base.py`, the three strategy modules, and `factory.py` together
   (`_apply_strategy` removal must be atomic with the async signature
   change so neither side breaks the other).
2. Update `Session` call sites (`acompletion`, `create`,
   `set_message_context_strategy`) in the same commit.
3. Update tests that called `_apply_strategy` or `create()` directly.
4. Run `ruff check`, `mypy server/`, and the full pytest suite.
5. Run `openspec validate consolidate-context-strategy-methods`.

There is no production data migration: persisted `SessionState` JSON is
unchanged in shape, and rehydration goes through the same factory entry
point (just without `await`).
