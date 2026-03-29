## Context

Domain model files (`session.py`, `llm_stats_decorator.py`, `context_strategy.py`) import `CompletionEvent`, `TextChunkEvent`, `CompletionDoneEvent`, and `ILlmPort` from `server.application.port.outbound.llm_port`. Meanwhile, `llm_port.py` itself imports `CompletionConfig`, `StopReason`, `TokensUsage` from `server.application.domain.model.completion`. This creates a bidirectional dependency between the innermost domain model layer and the port layer, violating hexagonal architecture's dependency rule.

## Goals / Non-Goals

**Goals:**

- Eliminate the cyclic dependency between `domain/model/` and `port/outbound/`
- Ensure domain model has zero imports from `port/`
- Preserve all existing public API signatures and runtime behavior

**Non-Goals:**

- Refactoring `ILlmPort` method signatures
- Changing event class fields or validation logic
- Introducing new abstractions or event bus patterns

## Decisions

### Decision 1: Create `domain/model/llm_events.py` for event classes

Move `CompletionEvent`, `TextChunkEvent`, and `CompletionDoneEvent` into a new file `server/application/domain/model/llm_events.py`.

**Rationale:** These events are domain concepts — they describe what happened during a completion, not how the port is wired. Keeping them separate from `completion.py` avoids bloating that file and makes the event hierarchy easy to find. The port module (`llm_port.py`) will import events from the model layer, restoring correct dependency direction.

**Alternative considered:** Merge events into `completion.py`. Rejected because `completion.py` already defines config and value objects — mixing in event classes reduces cohesion.

### Decision 2: `ILlmPort` stays in `port/outbound/llm_port.py`

The protocol definition remains in the port layer. It will import event types from `domain/model/llm_events.py` and config types from `domain/model/completion.py`. This is the correct direction: port depends on model.

**Rationale:** `ILlmPort` is the contract adapters must satisfy — it belongs in the port layer by definition.

### Decision 3: Re-export events from `llm_port.py` for backward compatibility during transition

After moving events, `llm_port.py` will re-export them so that existing adapter imports (`from server.application.port.outbound.llm_port import TextChunkEvent`) continue to work without changes.

**Rationale:** This limits the blast radius of the refactoring. Adapter code can be updated to import directly from `domain/model/llm_events` in a follow-up cleanup, but it is not required for correctness since adapters are allowed to depend on both ports and model.

## Risks / Trade-offs

- **[Risk] Stale imports in tests** → Grep for all imports of event types and update. Tests currently import from `port/outbound/llm_port`; these must be redirected.
- **[Risk] Re-exports mask the real source** → Acceptable short-term. Re-exports can be removed once all consumers are updated.
