## 1. Domain model changes — MessageContextStrategy

- [x] 1.1 Add `MessageContextStrategyDefaults` data model to `context_strategy.py` (type, completion_config, metadata). Write unit tests for construction and default values per spec scenarios.
- [x] 1.2 Remove `MessageContextStrategyFactory.default()` method. Update any references.
- [x] 1.3 Write/update unit tests for `MessageContextStrategyFactory.build()` verifying all spec scenarios (dummy, sliding_window, summary, unknown type raises ValueError, llm passthrough). Verify `default()` no longer exists.

## 2. Domain model changes — Session

- [x] 2.1 Add `SessionState` data model to `session.py` (id, created_at, completion_config, statistics, strategy_type, strategy_metadata, strategy_completion_config, strategy_records). Write unit tests for construction and default values per spec scenarios.
- [x] 2.2 Remove `SessionDto` from `session.py`. Remove `Session.to_dto()` and `Session.from_dto()` methods.
- [x] 2.3 Add `message_context_strategy` read-only property to `Session`. Update `Session.__init__` signature to accept pre-built `usage_stats: SessionUsageStats` and `message_context_strategy: MessageContextStrategy` (no internal strategy building). Update `Session.create()` to build strategy then delegate to `__init__`.
- [x] 2.4 Write/update unit tests for `Session` construction, `create()`, `message_context_strategy` property, and `statistics` property per spec scenarios.

## 3. Domain model changes — completion.py

- [x] 3.1 Remove `MessageContextStrategyConfig` from `completion.py`. Remove all imports of it across the codebase.

## 4. Port interface changes

- [x] 4.1 Update `ISessionRepository` port: `create_session(session: Session)`, `update_session(session: Session)`, `get_session(id: str) -> SessionState`. Update imports.

## 5. Config and infrastructure changes

- [x] 5.1 Update `ServerConfig` in `config_loader.py`: remove `message_context_strategy_config`, add `message_context_strategies_path: str` and `default_message_context_strategy: str`.
- [x] 5.2 Implement `load_message_context_strategies(path: str, base_dir: str) -> dict[str, MessageContextStrategyDefaults]` in `config_loader.py`. Resolve file references (`prompt_path`, `system_prompt_path`, `output_config_path`) relative to base_dir. Return dict keyed by strategy type.
- [x] 5.3 Update `get_server_config()`: remove `message_context_strategy_config` resolution, load strategies file via `load_message_context_strategies()`.
- [x] 5.4 Update `configs/server.json` to match new schema (remove `message_context_strategy_config`, ensure `message_context_strategies_path` and `default_message_context_strategy` fields).

## 6. Adapter changes — persistence

- [x] 6.1 Move/adapt `SessionDto` into `session_file_adapter.py` as an adapter-internal type (or merge with existing `SessionInfoDto`/`SessionMessagesDto`).
- [x] 6.2 Update `SessionFileAdapter.create_session()` and `update_session()` to accept `Session`, read its properties (id, created_at, completion_config, statistics, message_context_strategy.*), and map to internal DTOs for file I/O.
- [x] 6.3 Update `SessionFileAdapter.get_session()` to return `SessionState` instead of `SessionDto`. Map from file DTOs to `SessionState`.
- [x] 6.4 Verify correctness of MessageContextStrategy metadata serialization/deserialization for all subtypes (dummy: empty dict, sliding_window: window_size, summary: window_size + summary + summarization_prompt).
- [x] 6.5 Verify correctness of Session state round-trip: save via `create_session(session)`, load via `get_session(id)`, confirm all fields match.

## 7. Use case changes

- [x] 7.1 Update `CreateSessionUseCase.__init__` to accept `strategy_defaults: dict[str, MessageContextStrategyDefaults]` and `default_strategy_type: str` instead of `MessageContextStrategyConfig`. Update `execute()` to look up defaults and build strategy.
- [x] 7.2 Update `GetSessionUseCase` to reconstruct `Session` from `SessionState` returned by repository — build LLM ports, billing, strategy via `MessageContextStrategyFactory.build()`, and call `Session(...)`.
- [x] 7.3 Update `SendMessageUseCase` to pass `Session` (not DTO) to `repository.update_session()`.
- [x] 7.4 Write/update unit tests for `CreateSessionUseCase` with new constructor params and default strategy lookup.
- [x] 7.5 Write/update unit tests for `GetSessionUseCase` with `SessionState`-based reconstruction.

## 8. Composition root

- [x] 8.1 Update `app_factory.py`: load strategy defaults via `load_message_context_strategies()`, pass `strategy_defaults` and `default_strategy_type` to `CreateSessionUseCase`.
- [x] 8.2 Verify the application starts and basic session create/get/delete flow works end-to-end.
