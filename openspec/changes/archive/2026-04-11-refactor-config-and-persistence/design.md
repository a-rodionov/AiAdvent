## Context

The application follows hexagonal architecture with four layers: domain, use_cases, adapters, infrastructure. Currently:

- `ServerConfig` in `config_loader.py` embeds a single `MessageContextStrategyConfig` (from `completion.py`) which couples config to one strategy instance.
- `SessionDto` lives in `session.py` (domain layer) alongside `Session`, violating layer boundaries — persistence concerns leak into the domain.
- `Session.to_dto()` / `Session.from_dto()` methods force the domain aggregate to know its serialization format.
- `session_file_adapter.py` already defines adapter-level DTOs (`SessionInfoDto`, `SessionMessagesDto`, etc.) but still depends on the domain's `SessionDto` as an intermediary.
- A `message_context_strategies.json` file already exists with per-type defaults, but the app ignores it — it reads strategy config inline from `server.json`.

## Goals / Non-Goals

**Goals:**
- Server config references an external strategies file and a default strategy identifier — no inline strategy config.
- A domain-level data model holds strategy defaults; infrastructure loads them from the file.
- `SessionDto` and all DTO mapping live exclusively in the adapter layer.
- `Session` exposes properties and constructor params sufficient for external reconstruction.
- `ISessionRepository` port uses `Session` for writes and a domain-level `SessionState` for reads.
- Persistence read/write for Session and MessageContextStrategy are correct with the new structure.

**Non-Goals:**
- Backward compatibility with previously saved session files.
- Runtime strategy switching via API (existing `set_message_context_strategy` stays as-is).
- Changes to the TUI client or WebSocket protocol.

## Decisions

### D1: Remove `MessageContextStrategyConfig`, add file-based strategy defaults

**Choice:** Delete `MessageContextStrategyConfig` from `completion.py`. Replace with a new domain model `MessageContextStrategyDefaults` (in `context_strategy.py`) holding `type: str`, `completion_config: CompletionConfig`, `metadata: dict[str, Any]`.

`ServerConfig` gains two fields:
- `message_context_strategies_path: str` — path to JSON file.
- `default_message_context_strategy: str` — type identifier (e.g. `"dummy"`).

A new infrastructure function `load_message_context_strategies(path: str, base_dir: str) -> dict[str, MessageContextStrategyDefaults]` in `config_loader.py` reads and resolves the file (including `prompt_path`, `system_prompt_path` resolution), returning a dict keyed by strategy type.

**Rationale:** Separates strategy catalogue (what strategies exist and their defaults) from server config (which strategy to use). The file is read once at startup; the defaults dict is passed to the use case.

**Alternative considered:** Embedding all strategy configs inline in `server.json`. Rejected because it bloats the server config and mixes concerns.

### D2: `CreateSessionUseCase` receives defaults dict and default type

**Choice:** `CreateSessionUseCase.__init__` takes `strategy_defaults: dict[str, MessageContextStrategyDefaults]` and `default_strategy_type: str` instead of `MessageContextStrategyConfig`. On `execute()`, it looks up the defaults for `default_strategy_type`, uses `MessageContextStrategyFactory.build()` to create the strategy with those defaults, and passes the pre-built strategy to `Session.__init__`.

**Rationale:** The use case orchestrates domain objects — looking up defaults and building a strategy is orchestration. The domain's `MessageContextStrategyFactory.build()` remains the single mechanism for strategy instantiation.

**Alternative considered:** A dedicated `MessageContextStrategyDefaultsFactory` class. Rejected — it would just wrap a dict lookup + a call to `build()`, adding no value.

### D3: Move `SessionDto` and mapping to adapter layer

**Choice:** Remove `SessionDto`, `to_dto()`, and `from_dto()` from `session.py`. The adapter's `session_file_adapter.py` owns all DTOs (`SessionDto` becomes internal to the adapter, or is merged into the existing `SessionInfoDto`/`SessionMessagesDto`).

Introduce `SessionState` — a plain domain data class (in `session.py` or a dedicated file) representing the serializable snapshot of a session:

```
SessionState:
  id: str
  created_at: datetime
  completion_config: CompletionConfig
  statistics: dict[str, dict[str, ModelStats]] | None
  strategy_type: str
  strategy_metadata: dict[str, Any]
  strategy_completion_config: CompletionConfig
  strategy_records: list[MessageRecord]
```

`ISessionRepository` port changes:
- `create_session(session: Session)` — adapter reads Session properties, maps to file DTOs, writes.
- `update_session(session: Session)` — same.
- `get_session(id: str) -> SessionState` — adapter reads files, maps to SessionState.
- `get_session_ids()` and `delete_session()` stay unchanged.

**Rationale:** The domain defines what state a session has (`SessionState`). The adapter decides how to persist it (file DTOs, directory layout). The use case bridges them — it creates Session from SessionState + runtime dependencies (LLM ports, billing).

**Alternative considered:** Having `get_session` return `Session` directly. Rejected because the adapter would need LLM port factories and billing factories, making it too heavy.

### D4: Session exposes state via properties

**Choice:** Add a `message_context_strategy` property to `Session` returning the strategy object. The adapter reads:
- `session.id`, `session.created_at`, `session.completion_config` (existing)
- `session.statistics` → `SessionUsageStats` (existing, rename internally if needed)
- `session.message_context_strategy` → strategy object with `.strategy_type`, `.get_metadata()`, `.get_records()`, `.completion_config`

`Session.__init__` signature stays: `(llm, id, created_at, completion_config, billing, usage_stats, message_context_strategy)`. This is the reconstruction path.

Remove `Session.create()` class method. The use case handles new-session construction directly using the same `__init__` after building the strategy.

**Rationale:** The constructor already accepts all state. Exposing the strategy via a property completes the round-trip: properties for reading, constructor for writing. Removing `create()` avoids duplication with the use case's construction logic.

### D5: Remove `MessageContextStrategyFactory.default()`

**Choice:** Remove the `default()` static method. The concept of "default strategy" is now configuration-driven (`default_message_context_strategy` in server config), not hardcoded in the factory.

**Rationale:** The factory's `build()` method is sufficient — the use case decides what type and metadata to pass based on loaded defaults.

## Risks / Trade-offs

- **[Risk]** Use case and adapter both need to build strategy via `MessageContextStrategyFactory.build()` — duplication of orchestration logic.
  → **Mitigation**: The steps are straightforward (look up defaults, call build). Extract a helper if duplication becomes problematic. GetSessionUseCase already does this today.

- **[Risk]** `SessionState` resembles the old `SessionDto`, just at a different layer.
  → **Mitigation**: The semantic difference matters: `SessionState` is the domain's contract for what constitutes session state; adapter DTOs are free to evolve independently (file format changes don't ripple into the domain).

- **[Risk]** Breaking change in saved session files — no migration path.
  → **Mitigation**: Explicitly a non-goal per requirements. Old session directories can be deleted.
