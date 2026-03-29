## Context

Outbound ports (`ILlmPort`, `ISessionRepository`, `ILlmPortFactory`, `IModelBillingFactory`) are well-defined as Protocol/ABC interfaces. Inbound adapters, however, depend directly on concrete use case classes. The `port/inbound/` directory exists but is empty. This asymmetry means inbound adapters cannot be decoupled from service implementations.

Currently there are 5 use cases:

- `CreateSessionUseCase.execute(session_id: str) -> Session`
- `GetSessionUseCase.execute(session_id: str) -> Session`
- `DeleteSessionUseCase.execute(session_id: str) -> None`
- `ListSessionsUseCase.execute() -> list[str]`
- `SendMessageUseCase.execute(session: Session, prompt: str, is_stream_prefered: bool) -> AsyncGenerator[SessionEvent, None]`

## Goals / Non-Goals

**Goals:**

- Define a Protocol in `port/inbound/` for each use case
- Update inbound adapters to type-hint against protocols, not concrete classes
- Maintain structural subtyping — use case classes satisfy protocols without inheriting from them

**Non-Goals:**

- Changing use case method signatures or behavior
- Adding middleware, decorators, or cross-cutting concerns via ports (future work)
- Introducing a command/query bus or mediator pattern

## Decisions

### Decision 1: One Protocol per use case, single file

Define all five protocols in `server/application/port/inbound/use_cases.py`.

**Rationale:** Each protocol is 3-5 lines. Five separate files would be excessive. A single `use_cases.py` file mirrors how outbound ports are organized (one file per interface is used there because each has more surface area).

**Alternative considered:** One file per protocol. Rejected for five tiny protocols — adds navigation overhead with no cohesion benefit.

### Decision 2: Use `typing.Protocol`, not ABC

Consistent with outbound ports (`ILlmPort` is a Protocol). Use case classes already have matching `execute` methods — structural subtyping works out of the box with no changes to service code.

**Rationale:** No inheritance required. mypy verifies conformance statically. This is the established pattern in the project.

### Decision 3: Naming convention `I<Action>UseCase`

Protocol names: `ICreateSessionUseCase`, `IGetSessionUseCase`, `IDeleteSessionUseCase`, `IListSessionsUseCase`, `ISendMessageUseCase`.

**Rationale:** Matches the existing naming convention (`ILlmPort`, `ISessionRepository`) — prefix `I` for interfaces, suffix mirrors the concrete class name.

## Risks / Trade-offs

- **[Risk] Over-abstraction for small project** → The protocols are tiny and add minimal code. The benefit is architectural consistency and testability of adapters in isolation.
- **[Risk] Adapters need constructor changes** → Adapters currently receive concrete use case instances. Type hints change but runtime wiring stays the same — the composition root passes the same objects.
