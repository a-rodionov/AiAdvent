## 1. Base class — drop `_apply_strategy`, make `_get_context` async

- [x] 1.1 In `server/application/domain/model/context_strategy/base.py`, remove the abstract `_apply_strategy` method and its docstring. Confirm no other code in `base.py` references it.
- [x] 1.2 In `add_user_query`, remove the `await self._apply_strategy()` call. The method body becomes a single append to `self._records`. Keep the `async def` signature (callers await it).
- [x] 1.3 In `add_model_response`, remove the `await self._apply_strategy()` call. The method body becomes a single append to `self._records`. Keep the `async def` signature.
- [x] 1.4 Change the abstract `_get_context` signature to `async def _get_context(self) -> list[dict[str, str]]`. Update the docstring to note that the method is async and may perform side effects (e.g. LLM calls).
- [x] 1.5 Change `get_context` to `async def get_context`; replace `full_messages.extend(self._get_context())` with `full_messages.extend(await self._get_context())`. Keep the system-prompt-prepend behaviour exactly as it was.

## 2. DummyStrategy

- [x] 2.1 In `server/application/domain/model/context_strategy/dummy_strategy.py`, delete the `_apply_strategy` method entirely.
- [x] 2.2 Change `_get_context` signature to `async def _get_context(self) -> list[dict[str, str]]`. Body unchanged: `return [r.message for r in self._records]`.

## 3. SlidingWindowStrategy

- [x] 3.1 In `server/application/domain/model/context_strategy/sliding_window_strategy.py`, delete the `_apply_strategy` method entirely.
- [x] 3.2 Delete the `create` classmethod entirely.
- [x] 3.3 Change `_get_context` signature to `async def _get_context(self) -> list[dict[str, str]]`. Body unchanged: `return [r.message for r in self._records[-self._window_size:]]`. Do NOT add a trim of `self._records` here — the slice is the projection; `self._records` is the persistence shape.

## 4. SummaryStrategy

- [x] 4.1 In `server/application/domain/model/context_strategy/summary_strategy.py`, delete the `_apply_strategy` method entirely (its body moves into `_get_context` in the next step).
- [x] 4.2 Delete the `create` classmethod entirely.
- [x] 4.3 Rewrite `_get_context` as `async def _get_context(self) -> list[dict[str, str]]` with the following body:
  - (a) Compute `records_after_anchor` exactly as the old `_apply_strategy` did (full record list when `_summary.anchor_id is None`; else slice after the anchor index, falling back to the full list when the anchor id cannot be located).
  - (b) When `len(records_after_anchor) >= self._window_size`, build the LLM input (system prompt when configured, prior summary text as a user message when non-empty, then the records-after-anchor message dicts) and run the existing summarisation loop (`async for event in self._llm.acompletion(...)`, accumulate `assistant_text`). After the loop, set `self._summary = Summary(text=assistant_text, anchor_id=self._records[-1].id)`. Do NOT clear `self._records`.
  - (c) After the optional summarisation, recompute `records_after_anchor` against the (possibly just-updated) `_summary.anchor_id` and return: `[r.message for r in self._records]` when `_summary.anchor_id is None`; else `[{"role":"user","content": self._summary.text}] + [r.message for r in records_after_anchor]`.
- [x] 4.4 Preserve all existing logger calls in the new `_get_context` body (records-since-anchor count, system prompt log, updated-summary log).

## 5. Factory

- [x] 5.1 In `server/application/domain/model/context_strategy/factory.py`, change `build` from `async def build(...)` to `def build(...)`.
- [x] 5.2 Replace `await SummaryStrategy.create(...)` with a direct `SummaryStrategy(...)` constructor call (same arguments).
- [x] 5.3 Replace `await SlidingWindowStrategy.create(...)` with a direct `SlidingWindowStrategy(...)` constructor call (same arguments).

## 6. Session wiring

- [x] 6.1 In `server/application/domain/model/session.py`, change `Session.acompletion` to `await self._message_context_strategy.get_context()` (today it calls it without `await`).
- [x] 6.2 In `Session.create`, drop the `await` on `MessageContextStrategyFactory.build(...)` (factory is now sync). Method stays `async`.
- [x] 6.3 In `Session.set_message_context_strategy`, drop the `await` on `MessageContextStrategyFactory.build(...)`. Method stays `async`. Update its docstring to remove the "so `_apply_strategy()` runs immediately" wording (no apply step exists anymore).

## 7. Audit other call sites

- [x] 7.1 Run `Grep` across `server/`, `tests/`, `client.py`, `server.py` for `_apply_strategy`. Confirm zero remaining hits except in the now-deleted task notes.
- [x] 7.2 Run `Grep` for `\.create\(` on `SlidingWindowStrategy` and `SummaryStrategy`. Update every site to call the constructor directly.
- [x] 7.3 Run `Grep` for `await .*\.get_context\(` and for `\.get_context\(` (without await). Confirm every call site of `MessageContextStrategy.get_context` is awaited; flag and fix any that are not.
- [x] 7.4 Run `Grep` for `await MessageContextStrategyFactory.build` and for `MessageContextStrategyFactory.build` to confirm no leftover `await` keyword precedes `factory.build(...)`.

## 8. Tests — adapt existing

- [x] 8.1 In `tests/domain/entities/test_context_strategy.py`, replace every `await SlidingWindowStrategy.create(...)` and `await SummaryStrategy.create(...)` with the appropriate constructor call.
- [x] 8.2 Replace every `await s._apply_strategy()` with `await s.get_context()`. The intent (trigger the strategy's work) is preserved by the new lazy-on-read semantics.
- [x] 8.3 Update `test_apply_strategy_no_emit_token_usage_call` to inspect the source of `SummaryStrategy._get_context` instead of `_apply_strategy`. Rename to `test_get_context_no_emit_token_usage_call`.
- [x] 8.4 Update `test_does_not_trim_when_within_window` and `test_trims_oldest_records_when_over_window` to reflect that `get_history()` returns the full untrimmed list — assert the windowing via `await s.get_context()` instead, and assert `s.get_history()` returns every record.
- [x] 8.5 Update `test_get_history_returns_raw_records` (SlidingWindow) so it asserts the full record count, not the windowed count.
- [x] 8.6 Update `test_add_user_query_then_apply_strategy_trims` (SlidingWindow): rename to reflect the new behaviour and assert that `get_history()` includes every appended record while `await get_context()` returns only the last `window_size`.
- [x] 8.7 Update every async test on `MessageContextStrategyFactory.build` to drop `await` and become a synchronous test (or keep `async` but call `MessageContextStrategyFactory.build(...)` without `await`).
- [x] 8.8 In any test that asserts `await s.get_context()`-style behaviour, ensure `get_context` is awaited (the call now returns a coroutine).
- [x] 8.9 Update `tests/domain/entities/test_session.py` (and any other Session test) so any test that called `await session._message_context_strategy.get_context()` or that relied on summarisation firing inside `add_*` is rewritten to expect summarisation to fire inside `get_context()` instead.
- [x] 8.10 Update `tests/use_cases/conftest.py` and any use-case fixtures that build strategies via `await ... .create(...)` or `await MessageContextStrategyFactory.build(...)` to drop the `await` (or call the constructor).

## 9. Tests — TDD additions for new requirements

- [x] 9.1 Add a test asserting `MessageContextStrategy.add_user_query` does not call `_apply_strategy` (use `inspect.getsource` and assert the substring `_apply_strategy` is absent).
- [x] 9.2 Add the same test for `MessageContextStrategy.add_model_response`.
- [x] 9.3 Add a test for each strategy class asserting `assert not hasattr(<Strategy>, "_apply_strategy")`.
- [x] 9.4 Add a test for `SlidingWindowStrategy` and `SummaryStrategy` asserting `assert not hasattr(<Strategy>, "create")`.
- [x] 9.5 Add a test for `MessageContextStrategyFactory.build` asserting `inspect.iscoroutinefunction(MessageContextStrategyFactory.build) is False`.
- [x] 9.6 Add a test that `inspect.iscoroutinefunction(MessageContextStrategy.get_context) is True` and the same for each subclass's `_get_context`.
- [x] 9.7 Add a `SummaryStrategy` test: append `window_size` records via `add_user_query` / `add_model_response` (no `get_context` call); assert `self._llm.acompletion` was NOT called and `_summary` is unchanged. Then call `await get_context()` once; assert `self._llm.acompletion` was called exactly once and `_summary` rotated.
- [x] 9.8 Add a `SlidingWindowStrategy` test: append `window_size + 5` records and assert `len(s.get_history()) == window_size + 5` while `len(await s.get_context())` equals `window_size` (plus 1 for system prompt when configured).

## 10. Final validation

- [x] 10.1 Run `./run_tests.sh` and confirm the full suite passes.
- [x] 10.2 Run `./run_tests.sh --cov` and confirm coverage does not regress on `server/application/domain/model/context_strategy/` or `server/application/domain/model/session.py`.
- [x] 10.3 Run `.venv/bin/python -m ruff check .` and `.venv/bin/python -m ruff format --check .`.
- [x] 10.4 Run `.venv/bin/python -m mypy server/`. Investigate any reported "missing await" — those indicate unconverted call sites.
- [x] 10.5 Run `openspec validate consolidate-context-strategy-methods --strict` to confirm the change is consistent with its specs.
