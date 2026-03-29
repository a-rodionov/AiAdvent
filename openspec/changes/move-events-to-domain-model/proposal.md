## Why

Domain model files (`session.py`, `llm_stats_decorator.py`, `context_strategy.py`) import event types (`CompletionEvent`, `TextChunkEvent`, `CompletionDoneEvent`) and the `ILlmPort` protocol from `port/outbound/llm_port.py`. This creates a cyclic dependency between `domain/model/` and `port/outbound/` — the innermost hexagon layer depends on the port layer, violating the fundamental dependency direction rule of hexagonal architecture.

## What Changes

- **Move event classes** (`CompletionEvent`, `TextChunkEvent`, `CompletionDoneEvent`) from `port/outbound/llm_port.py` to `domain/model/` (new file `domain/model/llm_events.py` or merged into `completion.py`).
- **Remove model → port imports**: domain model files will import events from `domain/model/` instead of `port/outbound/`.
- **Update `ILlmPort`** in `port/outbound/llm_port.py` to import event types from `domain/model/` (port depends on model — correct direction).
- **Update all adapter imports** that reference the moved event types.

## Capabilities

### New Capabilities

_(none — this is an internal refactoring)_

### Modified Capabilities

- `llm-port-contract`: Event types (`CompletionEvent`, `TextChunkEvent`, `CompletionDoneEvent`) move from the port module to the domain model. The `ILlmPort` protocol signature stays the same but its event type imports change origin.

## Impact

- **Files modified**: `server/application/port/outbound/llm_port.py`, `server/application/domain/model/session.py`, `server/application/domain/model/llm_stats_decorator.py`, `server/application/domain/model/context_strategy.py`, all adapter files importing events.
- **No API changes**: public interfaces remain identical; only import paths change.
- **Tests**: import paths in tests referencing event types will need updating.
