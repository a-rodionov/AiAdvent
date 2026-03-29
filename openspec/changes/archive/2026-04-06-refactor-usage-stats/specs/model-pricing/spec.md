## REMOVED Requirements

### Requirement: UsageStatistics compound statistics model
**Reason**: Replaced by `ModelStats` NamedTuple in the `usage-stats` capability. `UsageStatistics` was a Pydantic model that existed solely to bundle `TokensUsage` + optional `TokensCost`; it required a circular-import shim because `TokensUsage` lives in `completion.py`. `ModelStats` is lighter, has no circular-import issue, and keeps the type in the module that owns accumulation.
**Migration**: Replace all references to `UsageStatistics` with `ModelStats` from `app.domain.value_objects.usage_stats`.

---

## MODIFIED Requirements

### Requirement: TokensCost accumulated cost model
`TokensCost` is a Pydantic `BaseModel` representing accumulated monetary cost in currency units. It SHALL carry: `prompt_tokens` (float, default `0.0`, ≥ 0), `completion_tokens` (float, default `0.0`, ≥ 0), and `total_tokens` (float, default `0.0`, ≥ 0). Negative values for any field SHALL be rejected by Pydantic validation.

#### Scenario: all fields default to zero
- **WHEN** `TokensCost` is constructed with no arguments
- **THEN** `prompt_tokens`, `completion_tokens`, and `total_tokens` are all `0.0`

#### Scenario: positive values are accepted
- **WHEN** `TokensCost` is constructed with positive float values
- **THEN** the fields hold the provided values

#### Scenario: negative prompt_tokens raises ValidationError
- **WHEN** `TokensCost` is constructed with `prompt_tokens=-0.001`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: negative completion_tokens raises ValidationError
- **WHEN** `TokensCost` is constructed with `completion_tokens=-0.001`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: negative total_tokens raises ValidationError
- **WHEN** `TokensCost` is constructed with `total_tokens=-0.001`
- **THEN** `pydantic.ValidationError` is raised
