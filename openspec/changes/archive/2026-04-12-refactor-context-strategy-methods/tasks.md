## 1. Package scaffolding and base class

- [x] 1.1 Create directory `server/application/domain/model/context_strategy/`.
- [x] 1.2 Move `MessageRecord` (NamedTuple), `MessageContextStrategyDefaults` (Pydantic model), and `MessageContextStrategy` (abstract base) from the flat `context_strategy.py` into `context_strategy/base.py`. Do not copy subclasses or factory yet.
- [x] 1.3 In `base.py`, rewrite `MessageContextStrategy.get_history()` to return `list(self._records)` (raw `MessageRecord` list) and mark it non-overridable (docstring + `Final`-ish comment). Remove the `get_records()` method entirely.
- [x] 1.4 In `base.py`, add the new `get_context()` concrete method that prepends the system prompt (when configured) then extends with the abstract `_get_context()`. Replace the existing abstract `_get_history()` with a new abstract `_get_context()`; update abstract-method decorators and docstrings.

## 2. Concrete strategy modules

- [x] 2.1 Create `context_strategy/dummy_strategy.py` with `DummyStrategy`. Implement `_get_context()` as `[r.message for r in self._records]` (inheriting the base `get_context()` behaviour). Keep `_apply_strategy` as a no-op and `get_metadata()` returning `{}`. Remove any residual `_get_history()` code.
- [x] 2.2 Create `context_strategy/sliding_window_strategy.py` with `SlidingWindowStrategy`. Implement `_get_context()` as `[r.message for r in self._records[-self._window_size:]]`. Preserve the existing `window_size` validation, `create()` classmethod, and `_apply_strategy` trimming logic. Remove any residual `_get_history()` code.
- [x] 2.3 Create `context_strategy/summary_strategy.py` with the `Summary` NamedTuple (`text: str`, `anchor_id: UUID | None`) and `SummaryStrategy`. Change `_summary` to be a `Summary` instance; accept `summary: Summary` in the constructor (default `Summary("", None)`).
- [x] 2.4 In `SummaryStrategy`, replace the trigger: count records after `_summary.anchor_id` (fall back to the full record count when `anchor_id is None`); only run summarisation logic when that count is `>= window_size`.
- [x] 2.5 In `SummaryStrategy._apply_strategy`, build the LLM input as `[previous-summary user message if text non-empty]` + `[records after anchor as message dicts]` (plus system prompt when configured). Call `self._llm.acompletion`, capture the assistant text, replace `self._summary` with `Summary(text=new_text, anchor_id=self._records[-1].id)`. Do **NOT** clear `self._records`.
- [x] 2.6 In `SummaryStrategy._get_context`, return `[r.message for r in self._records]` when `_summary.anchor_id is None`; otherwise return `[{"role":"user","content": self._summary.text}]` + `[r.message for r in records_after_anchor]`.
- [x] 2.7 Update `SummaryStrategy.get_metadata()` to emit `{"window_size", "summary_text", "summary_anchor_id", "summarization_prompt"}`, with `summary_anchor_id` as the string form of the UUID or `None`.

## 3. Factory

- [x] 3.1 Create `context_strategy/factory.py` with `MessageContextStrategyFactory`. Import each concrete strategy from its sibling module. Preserve the existing `build(strategy_type, metadata, records, llm, completion_config)` signature.
- [x] 3.2 Update the `"summary"` branch of `build` to read `summary_text`, `summary_anchor_id` (parse with `UUID(...)` when present), and `summarization_prompt` from metadata; pass `summary=Summary(text=summary_text, anchor_id=parsed_anchor)` into the strategy.

## 4. Package entry point and module deletion

- [x] 4.1 Create `context_strategy/__init__.py` that re-exports: `MessageRecord`, `MessageContextStrategyDefaults`, `MessageContextStrategy`, `DummyStrategy`, `SlidingWindowStrategy`, `SummaryStrategy`, `Summary`, `MessageContextStrategyFactory`.
- [x] 4.2 Delete the flat `server/application/domain/model/context_strategy.py` module.
- [x] 4.3 Run `ruff check` and `mypy server/` to confirm every import site still resolves through the new package.

## 5. Session wiring

- [x] 5.1 In `server/application/domain/model/session.py`, change `Session.acompletion` to call `self._message_context_strategy.get_context()` (not `get_history()`) when building the LLM request.
- [x] 5.2 In `Session.set_message_context_strategy`, replace `self._message_context_strategy.get_records()` with `self._message_context_strategy.get_history()` for the record transplant.
- [x] 5.3 Update `Session.messages` property (or any other caller inside `session.py`) that previously relied on `get_history()` returning message dicts; if it was wired to the LLM shape, point it at `get_context()` — if it was wired to persistence, leave it on `get_history()`. Document the choice in the code via a short docstring.
- [x] 5.4 Audit every other call site of `get_history` / `get_records` across the repo (`server/`, `tests/`, adapters, use-cases). Point each one at the correct new method: persistence shape → `get_history()`, LLM shape → `get_context()`.

## 6. Tests

- [x] 6.1 Add unit tests for `DummyStrategy.get_context()`, `get_history()`, and the new base `get_context()` system-prompt prepend behaviour. Verify `get_records` no longer exists on any strategy.
- [x] 6.2 Add unit tests for `SlidingWindowStrategy.get_context()` returning only the last `window_size` message dicts, and `get_history()` returning the raw (already-trimmed) record list.
- [x] 6.3 Add unit tests for `SummaryStrategy` covering: trigger below / at / above window after anchor, anchor update on summarisation, records preserved across summarisation, `get_context()` with and without anchor, `get_metadata()` round-trip through `MessageContextStrategyFactory.build()`, and `Summary` NamedTuple identity.
- [x] 6.4 Update `Session` tests: `acompletion` passes the value of `get_context()` to the LLM port, not `get_history()`; `set_message_context_strategy` transplants records via `get_history()`.
- [x] 6.5 Delete or rewrite any existing test that asserts `SummaryStrategy` clears `_records` after summarisation — the new behaviour preserves them.
- [x] 6.6 Run `./run_tests.sh` and confirm the full suite passes. Run `./run_tests.sh --cov` and confirm coverage does not regress on the touched modules.

## 7. Final validation

- [x] 7.1 Run `.venv/bin/python -m ruff check .` and `.venv/bin/python -m ruff format --check .`.
- [x] 7.2 Run `.venv/bin/python -m mypy server/`.
- [x] 7.3 Run `openspec validate refactor-context-strategy-methods` to confirm the change is consistent with its specs.
