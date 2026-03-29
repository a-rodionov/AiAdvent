## ADDED Requirements

### Requirement: TokensUsage defined in usage-stats module
The usage-stats module SHALL define the `TokensUsage` model, representing raw token counts (`prompt_tokens`, `completion_tokens`) for a single completion. Code that needs `TokensUsage` SHALL import it from the usage-stats module, not from the completion module.

#### Scenario: TokensUsage accessible from usage-stats module
- **WHEN** a consumer imports `TokensUsage`
- **THEN** it SHALL import from `server.application.domain.model.usage_stats`
