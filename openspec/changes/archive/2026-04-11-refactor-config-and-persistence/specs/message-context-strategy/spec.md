## ADDED Requirements

### Requirement: MessageContextStrategyDefaults data model
`MessageContextStrategyDefaults` is a domain data class representing the default configuration for one strategy type. It SHALL carry: `type` (non-empty string — the strategy type identifier, e.g. `"dummy"`, `"summary"`, `"sliding_window"`), `completion_config` (CompletionConfig — the LLM configuration for the strategy), and `metadata` (dict with default `{}` — type-specific defaults such as `window_size`, `summarization_prompt`). This model is defined in the domain layer alongside strategy classes and is used by `CreateSessionUseCase` to create strategies with file-driven defaults.

#### Scenario: defaults carry type and completion_config
- **WHEN** `MessageContextStrategyDefaults` is constructed with `type="summary"` and a `CompletionConfig`
- **THEN** `defaults.type` is `"summary"` and `defaults.completion_config` matches the provided config

#### Scenario: metadata defaults to empty dict
- **WHEN** `MessageContextStrategyDefaults` is constructed without providing `metadata`
- **THEN** `defaults.metadata` is `{}`

#### Scenario: metadata carries type-specific defaults
- **WHEN** `MessageContextStrategyDefaults` is constructed with `metadata={"window_size": 4, "summarization_prompt": "Summarize..."}`
- **THEN** `defaults.metadata["window_size"]` is `4` and `defaults.metadata["summarization_prompt"]` is `"Summarize..."`

---

## MODIFIED Requirements

### Requirement: MessageContextStrategyFactory — build and restore strategies

`MessageContextStrategyFactory.build(strategy_type, metadata, records, llm, completion_config)` SHALL reconstruct a strategy from its serialised state. The `llm` parameter is an `ILlmPort`-compatible object (which will be a `LlmStatsDecorator` when called from Session). The `default()` static method is REMOVED — the concept of a default strategy is now configuration-driven via `MessageContextStrategyDefaults` and the `default_message_context_strategy` server config parameter, not hardcoded in the factory.

#### Scenario: build with type "dummy" returns DummyStrategy

- **WHEN** `build("dummy", {}, [], llm, config)` is called
- **THEN** a `DummyStrategy` instance is returned

#### Scenario: build with type "sliding_window" returns SlidingWindowStrategy with default window 8

- **WHEN** `build("sliding_window", {}, [], llm, config)` is called with no `window_size` in metadata
- **THEN** a `SlidingWindowStrategy` instance is returned with `window_size=8`

#### Scenario: build with type "sliding_window" honours metadata window_size

- **WHEN** `build("sliding_window", {"window_size": 5}, [], llm, config)` is called
- **THEN** the returned strategy has `window_size=5`

#### Scenario: build with type "summary" returns SummaryStrategy with default window 4

- **WHEN** `build("summary", {"summary": ""}, [], llm, config)` is called with no `window_size` in metadata
- **THEN** a `SummaryStrategy` instance is returned with `window_size=4`

#### Scenario: build with type "summary" restores prior summary text

- **WHEN** `build("summary", {"window_size": 3, "summary": "prior"}, [], llm, config)` is called
- **THEN** the returned strategy's metadata contains `summary="prior"`

#### Scenario: build with unknown type raises ValueError
- **WHEN** `build("nonexistent", {}, [], llm, config)` is called
- **THEN** a `ValueError` is raised with a message containing "Unknown strategy type"

#### Scenario: build passes llm to strategy constructor
- **WHEN** `build("summary", metadata, records, llm_stats_decorator, config)` is called
- **THEN** the created `SummaryStrategy` stores `llm_stats_decorator` as its `_llm`

#### Scenario: default() method does not exist
- **WHEN** a developer inspects `MessageContextStrategyFactory`
- **THEN** there is no `default` method — default strategy selection is handled by configuration
