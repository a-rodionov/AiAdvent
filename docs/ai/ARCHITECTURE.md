# Architecture

Hexagonal (Ports & Adapters) architecture under `server/`:

## Packages

### adapter/

Concrete implementations that connect the application to the outside world.

- **`inbound/web/`** — Driving adapters: REST controllers, WebSocket handlers, HTTP schemas, protocol frames. Call into domain services (input ports).
- **`outbound/llm/`** — Driven adapter: LLM provider integration via any-llm SDK.
- **`outbound/persistence/`** — Driven adapter: file-based storage.

Imports from `application/` (domain model, ports, services). **Never imported by application code.**

### application/

The hexagon — all domain logic lives here.

- **`domain/model/`** — Entities, value objects. Pure Python, no I/O. Pydantic is allowed for data validation and serialization of value objects and entities.
- **`domain/service/`** — Scenarios. Orchestrate domain model objects. Import only from `domain/model/`, `port/inbound/`, `port/outbound/`.
- **`port/inbound/`** — Input port interfaces.
- **`port/outbound/`** — Output port interfaces. Defined as Protocols/ABCs. Implemented by outbound adapters.

### common/

Pure Python dataclasses/ABCs/Pydantic models with common logic able to reused at any layer.

### server.py, client.py

Framework wiring, config loading, app factory, shared helpers.
Imports everything; wires adapters to ports.

## Dependency Direction

```
server.py, client.py → adapter → application/domain/service → application/domain/model
                                                            → application/port/inbound
                                                            → application/port/outbound
```

Each layer may only import from layers to its right. Violations break the architecture.
