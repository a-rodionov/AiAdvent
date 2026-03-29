## ADDED Requirements

### Requirement: ILlmPortFactory port interface
`ILlmPortFactory` SHALL be a Protocol in the domain layer defining a single method `create(session_id: str, completion_config: CompletionConfig) -> ILlmPort`. It serves as a factory port for creating `ILlmPort` instances based on session identity and completion configuration.

#### Scenario: create returns an ILlmPort-compatible object
- **WHEN** `factory.create(session_id="sess-1", completion_config=config)` is called
- **THEN** the returned object satisfies the `ILlmPort` Protocol

#### Scenario: create uses provider from completion_config
- **WHEN** `factory.create` is called with a `CompletionConfig` having `provider="anthropic"`
- **THEN** the returned `ILlmPort` is configured for the `"anthropic"` provider

---

### Requirement: LlmPortFactoryAdapter caching behavior
`LlmPortFactoryAdapter` SHALL implement the `ILlmPortFactory` Protocol. It SHALL maintain a nested dictionary cache: `dict[str, dict[str, LlmAdapter]]` keyed by `session_id` (outer) and `provider` (inner, extracted from `completion_config.provider`). When `create` is called, if an `LlmAdapter` already exists for the `(session_id, provider)` pair, it SHALL return the existing instance. Otherwise, it SHALL create a new `LlmAdapter(provider)`, store it in the cache, and return it.

#### Scenario: first call creates a new adapter
- **WHEN** `create("sess-1", config)` is called for the first time
- **THEN** a new `LlmAdapter` is created and returned

#### Scenario: second call with same session and provider returns cached adapter
- **WHEN** `create("sess-1", config)` is called twice with the same provider
- **THEN** both calls return the same `LlmAdapter` instance (identity check)

#### Scenario: different sessions get different adapters
- **WHEN** `create("sess-1", config)` and `create("sess-2", config)` are called with the same provider
- **THEN** each call returns a different `LlmAdapter` instance

#### Scenario: different providers within same session get different adapters
- **WHEN** `create("sess-1", config_anthropic)` and `create("sess-1", config_openai)` are called
- **THEN** each call returns a different `LlmAdapter` instance
