## MODIFIED Requirements

### Requirement: UsageStats is a Protocol
`UsageStats` SHALL be a `typing.Protocol` defining the interface for token usage accumulation. It SHALL declare the method `add_stats(provider: str, model: str, usage: TokensUsage, cost: TokensCost | None = None) -> None`. Classes satisfying this protocol can be used interchangeably — specifically, `SessionUsageStats` satisfies `UsageStats` structurally.

The concrete `UsageStats` class (the current mutable accumulator) SHALL continue to exist and implement this protocol. Its construction, `zero()`, `add_stats()`, `data` property, and truthiness behavior remain unchanged.

#### Scenario: UsageStats is a Protocol
- **WHEN** a developer inspects `UsageStats` in `app/domain/value_objects/usage_stats.py`
- **THEN** it inherits from `typing.Protocol`

#### Scenario: concrete UsageStats still works as before
- **WHEN** `UsageStats()` is constructed and `add_stats` is called
- **THEN** it accumulates stats identically to the current behavior

#### Scenario: SessionUsageStats satisfies UsageStats Protocol
- **WHEN** a `SessionUsageStats` instance is passed to a function typed as `UsageStats`
- **THEN** mypy accepts it without type errors
