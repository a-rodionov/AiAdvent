## Context

`Session` lives in `app/domain/entities/session.py` and is the aggregate root of the conversation domain. It is a pure Python class (no framework imports) that owns an `ILlmPort`, a `ModelPricing` value object, a `CompletionConfig`, and a `MessageContextStrategy`. It is the only object that calls the LLM port directly for user-facing completions.

Key collaborators:
- **`MessageContextStrategy`** — controls which history records are sent to the LLM. Wired to session via `OnTokenUsage` so token counts flow back without coupling the strategy to pricing logic.
- **`ILlmPort`** — the hexagonal-architecture port for LLM access; injected at construction time.
- **`SessionDto`** — the Pydantic serialisation model used by the adapter layer (`SessionFileAdapter`) for persistence.
- **`update_statistics`** — module-level helper that accumulates `UsageStatistics` keyed by `"provider,model"`.

The change is **documentation-only**: a single `specs/session/spec.md` captures all behavioural contracts.

## Goals / Non-Goals

**Goals:**
- Produce `specs/session/spec.md` covering: `update_statistics`, `SessionDto`, session events (`SessionTextChunkEvent`, `SessionCompletionDoneEvent`), and the full `Session` aggregate root lifecycle.
- Every scenario must be independently testable and map to an existing test case in `tests/domain/entities/test_session.py`.

**Non-Goals:**
- No production code changes.
- No new domain logic or new strategies.
- No changes to `SessionDto` schema or the file adapter.

## Decisions

### Decision 1 — one spec file (`specs/session/spec.md`)
**Chosen:** All session-related types in a single spec.

**Alternatives considered:**
- Separate spec for `SessionDto` — the DTO only exists to serialise/deserialise `Session`; splitting would force readers to jump between files to understand the round-trip contract.
- Separate spec for `update_statistics` — it has no independent lifecycle and is only meaningful in the context of session statistics accounting.

**Rationale:** Session, its events, DTO, and statistics helper are a single cohesive subsystem. One file keeps cross-references natural.

### Decision 2 — per-request vs cumulative statistics are two distinct scopes
The spec must explicitly distinguish `SessionCompletionDoneEvent.statistics` (per-request, reset each call) from `Session.statistics` (cumulative across all calls). Conflating them is the most likely source of future misuse.

### Decision 3 — `set_message_context_strategy` rebuilds via factory
Rather than swapping the strategy reference directly, the session rebuilds the new strategy through `MessageContextStrategyFactory.build()` with the current records. This ensures `_apply_strategy()` runs immediately on the transplanted records — enforcing the new window before the next completion call.

## Risks / Trade-offs

- **Risk: spec scenarios become stale as Session evolves** → Mitigation: scenarios map 1-to-1 to test functions; CI test failures will flag divergence.
- **Risk: `_request_statistics` is reset at the start of `acompletion` before the LLM call.** If the LLM call raises, the previous request's per-request stats are silently discarded from the done event (but already committed to cumulative stats). Documented as known behaviour in the spec.
- **Trade-off: `from_dto` does not validate that `message_records` UUIDs form a consistent linked list** — it trusts the serialised state. The spec reflects this as a constraint (caller must provide valid serialised state).

## Open Questions

- Should `Session` expose a `reset_statistics()` method for long-running sessions where cumulative stats are no longer meaningful? Not needed today; left for future consideration.
