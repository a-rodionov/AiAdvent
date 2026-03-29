## Why

The architecture declares `port/inbound/` for input port interfaces, but the directory is empty. Inbound adapters (`session_routes.py`, `ws_handler.py`) import concrete use case classes directly (`CreateSessionUseCase`, `SendMessageUseCase`, etc.), coupling them to implementations rather than abstractions. This breaks hexagonal symmetry — outbound ports are properly abstracted via `ILlmPort`, `ISessionRepository`, etc., but inbound ports are missing entirely.

## What Changes

- **Define input port protocols** in `server/application/port/inbound/` — one Protocol per use case: `ICreateSession`, `IGetSession`, `IDeleteSession`, `IListSessions`, `ISendMessage`.
- **Use case classes** in `domain/service/` implicitly satisfy these protocols (structural subtyping, no inheritance needed).
- **Update inbound adapters** (`session_routes.py`, `ws_handler.py`) to depend on input port protocols instead of concrete use case classes.
- **Update composition root** (`app_factory.py`) to wire concrete use cases to the port type hints.

## Capabilities

### New Capabilities

- `inbound-port-contract`: Defines the input port Protocol interfaces for all use cases, specifying the contract that inbound adapters depend on.

### Modified Capabilities

_(none)_

## Impact

- **New files**: Protocol definitions in `server/application/port/inbound/`
- **Files modified**: `server/adapter/inbound/web/session_routes.py`, `server/adapter/inbound/web/ws_handler.py`, `server/common/app_factory.py` (or wherever the composition root lives after `relocate-composition-root`)
- **No behavior changes**: adapters call the same methods, just through protocol types
- **Type safety**: mypy will verify that use case classes conform to the inbound port protocols
