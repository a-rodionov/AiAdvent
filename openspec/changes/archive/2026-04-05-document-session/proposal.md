## Why

The `Session` aggregate root is the central orchestration object for every LLM conversation, yet it has no written specification — developers must read the implementation to discover its lifecycle, event model, statistics accounting, and DTO serialisation contract. Documenting it now pairs with the existing `message-context-strategy` spec to give the full domain layer a machine-readable contract.

## What Changes

- Add a specification for the `Session` aggregate root covering: construction (`create` factory), persistence round-trip (`to_dto` / `from_dto`), streaming completion (`acompletion`), strategy switching (`set_message_context_strategy`), and statistics accumulation.
- Document the `SessionEvent` hierarchy: `SessionTextChunkEvent` and `SessionCompletionDoneEvent`.
- Document `SessionDto` — the Pydantic persistence model and its validation rules.
- Document `update_statistics` — the helper that accumulates token usage and cost across providers/models.

## Capabilities

### New Capabilities

- `session`: Specification for the `Session` aggregate root, its event types, `SessionDto`, and the `update_statistics` helper — covering lifecycle, streaming, statistics accounting, and serialisation.

### Modified Capabilities

## Impact

- No production code changes; documentation only.
- Affects: `app/domain/entities/session.py`, `tests/domain/entities/test_session.py`, `app/adapters/repositories/session_file_adapter.py` (consumer of `SessionDto`), `app/use_cases/create_session.py` (consumer of `Session.create`).
