## Why

The server config currently embeds a single `MessageContextStrategyConfig` inline, coupling the config model to one strategy instance. This prevents supporting multiple strategy presets and makes it impossible to create sessions with different default strategies without changing the config structure. Additionally, `SessionDto` lives in the domain layer alongside `Session`, violating hexagonal architecture by placing a persistence concern (DTO) inside the domain model. Session's internal state is only accessible via `to_dto()`/`from_dto()` which forces the domain to know about its own serialization format.

## What Changes

- **BREAKING**: Remove `message_context_strategy_config` from `ServerConfig`. Replace with two new fields:
  - `message_context_strategies_path` (str) — path to a JSON file listing supported strategies with their default parameters.
  - `default_message_context_strategy` (str) — identifier of the strategy subtype to use when creating new sessions.
- Add a factory mechanism that reads the strategies file and creates strategy instances with defaults. Used by `CreateSessionUseCase` when building new sessions.
- **BREAKING**: Move `SessionDto` and adapter-level DTOs (`MessageRecordDto`, `MessageContextStrategyInfoDto`, `SessionInfoDto`, `SessionMessagesDto`) to the adapter layer (`server/adapter/outbound/persistence/`).
- Expose `Session` properties and constructor parameters sufficient for external code to extract and reconstruct session state without depending on a domain-level DTO.
- Update `MessageContextStrategy` and subtype persistence (serialization/deserialization) for correctness with the new config structure.
- Update `Session` persistence (save/load) for correctness with the restructured DTOs and config.
- No backward compatibility for previously saved session files.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `session`: SessionDto moves out of domain to adapter layer; Session exposes state properties/constructor for persistence without domain-level DTO dependency.
- `message-context-strategy`: Factory gains ability to create strategy instances from defaults loaded from an external config file; `MessageContextStrategyConfig` removed from domain.

## Impact

- **Config files**: `configs/server.json` structure changes (breaking). `configs/message_context_strategies.json` becomes the source of strategy defaults.
- **Domain model**: `server/application/domain/model/session.py` — `SessionDto` removed. `Session` gains properties for state access. `server/application/domain/model/completion.py` — `MessageContextStrategyConfig` removed.
- **Domain service**: `server/application/domain/service/create_session.py` — constructor changes to accept strategy factory/defaults instead of `MessageContextStrategyConfig`.
- **Adapter layer**: `server/adapter/outbound/persistence/session_file_adapter.py` — owns all persistence DTOs and mapping logic.
- **Config loader**: `server/common/config_loader.py` — `ServerConfig` model changes; new logic to load strategies file.
- **Composition root**: `server/common/app_factory.py` — wiring changes for new config shape.
- **Tests**: All tests involving session creation or strategy config need updating.
