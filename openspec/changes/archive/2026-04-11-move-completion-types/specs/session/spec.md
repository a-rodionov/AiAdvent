## ADDED Requirements

### Requirement: StopReason defined in session module
The session module SHALL define the `StopReason` enum, representing the reason a model generation turn ended (`stop`, `length`, `tool_calls`, `content_filter`). Code that needs `StopReason` SHALL import it from the session module, not from the completion module.

#### Scenario: StopReason accessible from session module
- **WHEN** a consumer imports `StopReason`
- **THEN** it SHALL import from `server.application.domain.model.session`
