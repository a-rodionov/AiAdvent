## ADDED Requirements

### Requirement: Inbound port protocols are defined for all use cases

`server/application/port/inbound/use_cases.py` SHALL define a `typing.Protocol` for each use case. Each protocol SHALL declare a single `execute` method matching the signature of its corresponding concrete use case class. The protocols are:

| Protocol                | Method signature                                                                                               |
| ----------------------- | -------------------------------------------------------------------------------------------------------------- |
| `ICreateSessionUseCase` | `execute(self, session_id: str) -> Session`                                                                    |
| `IGetSessionUseCase`    | `execute(self, session_id: str) -> Session`                                                                    |
| `IDeleteSessionUseCase` | `execute(self, session_id: str) -> None`                                                                       |
| `IListSessionsUseCase`  | `execute(self) -> list[str]`                                                                                   |
| `ISendMessageUseCase`   | `execute(self, session: Session, prompt: str, is_stream_prefered: bool) -> AsyncGenerator[SessionEvent, None]` |

#### Scenario: Protocol is a typing.Protocol

- **WHEN** a developer inspects any inbound port protocol
- **THEN** it inherits from `typing.Protocol`, not `abc.ABC`

#### Scenario: Structural subtyping works

- **WHEN** a concrete use case class implements `execute` with a matching signature without inheriting from the protocol
- **THEN** mypy accepts it wherever the protocol type is expected

### Requirement: Inbound adapters depend on port protocols, not concrete use case classes

Inbound adapter files (`session_routes.py`, `ws_handler.py`) SHALL type-hint their use case dependencies using the inbound port protocols. They SHALL NOT import concrete use case classes from `server.application.domain.service`.

#### Scenario: Adapter uses protocol type hint

- **WHEN** analyzing imports in `server/adapter/inbound/web/session_routes.py`
- **THEN** use case dependencies are typed as `ICreateSessionUseCase`, `IGetSessionUseCase`, etc. from `server.application.port.inbound.use_cases`
- **AND** no import references `server.application.domain.service`

#### Scenario: Adapter uses protocol type hint in ws_handler

- **WHEN** analyzing imports in `server/adapter/inbound/web/ws_handler.py`
- **THEN** use case dependencies are typed as `IGetSessionUseCase`, `ISendMessageUseCase` from `server.application.port.inbound.use_cases`
- **AND** no import references `server.application.domain.service`
