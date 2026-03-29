## Why

Today `MessageContextStrategy` exposes `get_history()` for both "what to persist" and "what to send to the LLM", backed by a parallel `get_records()` method for persistence. The two concerns have diverged enough that one method for each is clearer. At the same time, `SummaryStrategy` clears `_records` on every summarisation pass, which loses per-message provenance and prevents sessions from being restored to a full-history view. We want the summary to roll forward using an explicit *anchor* (UUID of the message the summary was last produced against) while `_records` keeps accumulating.

## What Changes

- **BREAKING**: `SummaryStrategy._summary` becomes a structured value `(text, anchor_id: UUID | None)` — the text plus the UUID of the last message the summary was produced against. Previously persisted summary metadata (plain string) will not rehydrate; no migration is provided.
- **BREAKING**: `SummaryStrategy._apply_strategy` triggers only when `window_size` or more records have accumulated *after* the anchor. On summarisation the new text and anchor overwrite the previous pair; `_records` is **not** cleared.
- **BREAKING**: `MessageContextStrategy.get_history()` becomes a single, non-overridable base implementation that returns `list(self._records)` (raw `MessageRecord`s). `Session` uses it for state persistence.
- Add `MessageContextStrategy.get_context()` (and per-strategy overrides) returning the ordered message dicts to send to the LLM next turn. `DummyStrategy` inherits the base implementation (`[r.message for r in self._records]`). `SummaryStrategy` returns `[{"role":"user","content": summary_text}]` followed by the records *after* the anchor (or all records when no summary is set). `SlidingWindowStrategy` returns the last `window_size` records. The system prompt, when configured, is prepended by the base `get_context()` so every strategy emits the same shape.
- **BREAKING**: `MessageContextStrategy.get_records()` is removed. Callers (`Session.set_message_context_strategy`, session persistence) switch to `get_history()`.
- **BREAKING**: `Session.acompletion()` now sends `get_context()` — not `get_history()` — to the LLM.
- Split `DummyStrategy`, `SummaryStrategy`, `SlidingWindowStrategy` into their own modules under `server/application/domain/model/context_strategy/`. `MessageContextStrategyFactory` imports from those modules. The public import path `from server.application.domain.model.context_strategy import ...` is preserved via package `__init__.py` re-exports.

## Capabilities

### New Capabilities

(none — this is a refactor of existing capabilities)

### Modified Capabilities

- `message-context-strategy`: summary anchor, `get_history` / `get_context` split, `get_records` removal, file/package split.
- `session`: `acompletion` uses `get_context`, `set_message_context_strategy` uses `get_history`, `Session.message_context_strategy` property documentation updated (no `get_records`).

## Impact

- Affected code:
  - `server/application/domain/model/context_strategy.py` → split into package `server/application/domain/model/context_strategy/` with `base.py`, `dummy_strategy.py`, `summary_strategy.py`, `sliding_window_strategy.py`, `factory.py`.
  - `server/application/domain/model/session.py` — swap `get_history` for `get_context` in `acompletion`; swap `get_records` for `get_history` in `set_message_context_strategy`.
  - Session persistence adapters that read `strategy_records` off `SessionState` — no shape change, but any that previously called `get_records()` directly must switch to `get_history()`.
  - Tests for `SummaryStrategy` (trigger condition, preservation of records, anchor update) and `Session` (acompletion uses `get_context`).
- Breaking for persisted data: sessions stored with `SummaryStrategy` metadata (plain string `summary`) cannot be rehydrated. Per user direction, no backwards-compatibility path is provided.
- External factory signature (`MessageContextStrategyFactory.build(...)`) is unchanged.
