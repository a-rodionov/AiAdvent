## Context

`MessageContextStrategy` today lives in a single module `server/application/domain/model/context_strategy.py` with three concrete subclasses (`DummyStrategy`, `SummaryStrategy`, `SlidingWindowStrategy`) and a `MessageContextStrategyFactory`. `Session` interacts with the strategy via:

- `get_history()` — returns message dicts, optionally prepended with the system prompt. Used both to feed the LLM (`Session.acompletion`) and to persist the session (via `get_records()` alongside, or by reading message dicts).
- `get_records()` — returns `list[MessageRecord]` for persistence (the records preserve UUID ids and prev-id links).

`SummaryStrategy` re-summarises whenever `len(_records) > window_size` and then clears `_records`, which makes it impossible for a caller to recover per-message history after summarisation and couples the trigger condition to a draining side-effect.

The two responsibilities that `get_history()` serves — "what to send to the LLM next turn" vs. "what to persist" — have drifted apart. The `SummaryStrategy` behaviour makes the drift visible: the persistence-side loses records every summarisation, and the LLM-side needs the summary prepended, which the persistence-side must then strip back off.

## Goals / Non-Goals

**Goals:**

- Split the two concerns cleanly: `get_history()` is the persistence shape, `get_context()` is the LLM-call shape.
- Make `SummaryStrategy` record-preserving by anchoring the summary to a specific `MessageRecord.id`; re-summarise only when enough new records have arrived beyond the anchor.
- Place each concrete strategy in its own module and keep `MessageContextStrategyFactory` decoupled from the subclasses' internals.
- Preserve the public import path `from server.application.domain.model.context_strategy import ...` so call-sites elsewhere in the codebase are unaffected by the module split.

**Non-Goals:**

- Migrating previously persisted sessions that used `SummaryStrategy` with the old plain-string `summary`. The user explicitly waived backwards compatibility.
- Changing `MessageContextStrategyFactory.build(...)` signature or its configuration-driven defaults.
- Introducing a new strategy type or changing `DummyStrategy` / `SlidingWindowStrategy` semantics beyond the method rename and the `get_context` addition.

## Decisions

### Decision: Summary anchor data model

`SummaryStrategy._summary` changes from a plain `str` to a small immutable value object — a `NamedTuple` `Summary(text: str, anchor_id: UUID | None)`. `anchor_id` is `None` before the first summarisation has happened and the UUID of the last message in `_records` at the moment the latest summary was produced afterwards.

Alternatives considered:

- **Two parallel attributes (`_summary_text`, `_summary_anchor_id`)**: works but fragments serialisation logic and invites the two to drift out of sync.
- **Pack the anchor into the text**: fragile; makes the LLM's output format load-bearing for state.

A `NamedTuple` keeps the value object immutable and trivially serialisable, matching the existing `MessageRecord` pattern in the module.

### Decision: `_apply_strategy` trigger condition

Trigger summarisation when the count of records appended **after** `_summary.anchor_id` (or from the start of `_records` when `anchor_id is None`) is greater than or equal to `window_size`. Otherwise `_apply_strategy` is a no-op.

Alternatives considered:

- **Keep `len(_records) > window_size`**: once we stop clearing records the condition becomes permanently true, causing the strategy to resummarise on every append.
- **Store the numeric index of the anchor**: breaks if records are ever reordered or pruned; the UUID is stable.

### Decision: Summarisation LLM input

On each summarisation pass, feed the LLM: `[{"role":"user","content": previous_summary_text}]` (when a previous summary exists) **plus** the records appended after the anchor — that is, the portion the previous summary does not yet cover. This matches the rolling-summary pattern and keeps the token cost of the summarisation call bounded by `window_size` plus the prior summary length, not by the total conversation length.

Alternatives considered:

- **Send full `_records` every time**: simple but defeats the strategy's purpose — cost grows linearly with conversation length.
- **Send only records after the anchor, discard the previous summary**: loses context across summarisation boundaries.

### Decision: `get_history()` and `get_context()` split

- `get_history()` — final, non-overridden. Returns `list(self._records)`. This is the persistence shape; `Session.set_message_context_strategy` and `SessionState`-reading adapters use it.
- `get_context()` — overridable. Returns `list[dict[str, str]]` — the ordered message dicts to send to the LLM next turn, with the system prompt prepended by the base implementation when `CompletionConfig.system_prompt` is non-empty. Per-strategy overrides append their trimmed/augmented view to the system prompt prefix.

Base `get_context()` body:

```python
def get_context(self) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if self._completion_config.system_prompt:
        messages.append({"role": "system", "content": self._completion_config.system_prompt})
    messages.extend(self._get_context())
    return messages
```

Each subclass implements `_get_context()`:

- `DummyStrategy._get_context()` → `[r.message for r in self._records]`
- `SummaryStrategy._get_context()` → if `_summary.anchor_id is None`: `[r.message for r in self._records]`; else `[{"role":"user","content": _summary.text}] + [r.message for r in records_after_anchor]`.
- `SlidingWindowStrategy._get_context()` → `[r.message for r in self._records[-self._window_size:]]`.

Alternatives considered:

- **Have each subclass implement `get_context()` directly without a `_get_context()` template**: repeats the system-prompt prepend in every subclass.
- **Put the system prompt in `get_history()`**: conflates persistence with presentation; the persisted state shouldn't carry a copy of a config-driven prompt.

### Decision: File / package split

Convert `context_strategy.py` into a package:

```
server/application/domain/model/context_strategy/
    __init__.py                 # re-exports: MessageRecord, MessageContextStrategyDefaults,
                                # MessageContextStrategy, DummyStrategy, SummaryStrategy,
                                # SlidingWindowStrategy, MessageContextStrategyFactory
    base.py                     # MessageRecord, MessageContextStrategyDefaults,
                                # MessageContextStrategy (with get_history + base get_context)
    dummy_strategy.py           # DummyStrategy
    summary_strategy.py         # Summary NamedTuple + SummaryStrategy
    sliding_window_strategy.py  # SlidingWindowStrategy
    factory.py                  # MessageContextStrategyFactory
```

`__init__.py` re-exports every symbol that was previously importable from the flat module, so `from server.application.domain.model.context_strategy import SummaryStrategy` keeps working.

Alternatives considered:

- **Leave as a single module**: works but the file already pushes past 220 lines and each strategy has its own test file aspiration.
- **Put each strategy under `strategies/`** and keep `context_strategy.py` as the base module: inconsistent with the rest of the domain layer, where modules use a flat directory.

## Risks / Trade-offs

- **Persisted session incompatibility** → No mitigation; the user explicitly waived backwards compatibility. Document in the proposal and in the release notes that any session with a stored `SummaryStrategy.summary` string will fail to rehydrate and must be recreated.
- **Unbounded `_records` growth** → Not mitigated in this change. Records accumulate for the life of a session; this is acceptable because (a) session lifetimes are bounded in practice and (b) `get_context()` still sends a bounded prefix to the LLM. Record-capping is a follow-up concern if it becomes a problem.
- **`get_context()` vs `get_history()` confusion** → Class docstrings and the updated spec make the split explicit; the method names telegraph intent.
- **Summarisation input behaviour is a judgement call** → The summarisation LLM call now receives the previous summary plus records-after-anchor rather than the full `_records`. This is efficient and matches the rolling-summary pattern but is a behavioural change. Tests lock it in.

## Migration Plan

1. Create the new `context_strategy/` package with `base.py`, `dummy_strategy.py`, `summary_strategy.py`, `sliding_window_strategy.py`, `factory.py`.
2. Implement the `Summary` NamedTuple and the new `SummaryStrategy` semantics (anchor-based trigger, record-preserving summarisation, updated `get_metadata()` including `summary_anchor_id`).
3. Add `get_context()` to the base class and override in `SummaryStrategy` and `SlidingWindowStrategy`; `DummyStrategy` inherits.
4. Remove `get_records()`; retarget `Session.set_message_context_strategy` and any session-state adapter to use `get_history()` (which now returns the record list).
5. Retarget `Session.acompletion` to call `get_context()`.
6. Delete the old `context_strategy.py` module. Confirm all imports resolve through the package `__init__.py`.
7. Update or replace tests: `SummaryStrategy` trigger/anchor/record-preservation, `Session.acompletion` uses `get_context`, `set_message_context_strategy` uses `get_history`, `Dummy` / `SlidingWindow` retain current semantics under the new method names.

No rollback plan beyond reverting the change — the refactor is atomic at the repo level.

## Open Questions

(none — clarification on `get_context()` slice semantics for `SummaryStrategy` resolved in favour of "messages after the anchor".)
