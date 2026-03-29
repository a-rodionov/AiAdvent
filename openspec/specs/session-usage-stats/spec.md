## Purpose

TBD — This capability defines the `SessionUsageStats` class that aggregates both per-invocation and lifecycle-total token usage statistics for a session, delegating to two internal `UsageStats` accumulators.

---

## Requirements

### Requirement: SessionUsageStats construction
`SessionUsageStats` SHALL be constructable with an optional `data` parameter of type `dict[str, dict[str, ModelStats]] | None`. When `data` is provided, it SHALL initialize `_lifecycle_total` as `UsageStats(data=data)`. When `data` is `None` or omitted, `_lifecycle_total` SHALL be initialized as an empty `UsageStats()`. In both cases, `_current_invocation` SHALL be initialized as an empty `UsageStats()`.

#### Scenario: default construction
- **WHEN** `SessionUsageStats()` is called with no arguments
- **THEN** both `_lifecycle_total` and `_current_invocation` are empty (falsy)

#### Scenario: construction with existing data
- **WHEN** `SessionUsageStats(data={"anthropic": {"claude-3": ModelStats(usage=TokensUsage(prompt_tokens=100, completion_tokens=50))}})` is called
- **THEN** `_lifecycle_total` contains the provided data and `_current_invocation` is empty

---

### Requirement: SessionUsageStats.add_stats delegates to both members
`SessionUsageStats.add_stats(provider, model, usage, cost=None)` SHALL call `_current_invocation.add_stats(provider, model, usage, cost)` and `_lifecycle_total.add_stats(provider, model, usage, cost)` with the same arguments. The method signature SHALL match `UsageStats.add_stats`.

#### Scenario: stats added to both members
- **WHEN** `add_stats("anthropic", "claude-3", TokensUsage(prompt_tokens=10, completion_tokens=5))` is called
- **THEN** both `_current_invocation` and `_lifecycle_total` contain an entry for `("anthropic", "claude-3")` with matching values

#### Scenario: multiple calls accumulate in both
- **WHEN** `add_stats` is called twice with `prompt_tokens=10` each time
- **THEN** both `_current_invocation` and `_lifecycle_total` show `prompt_tokens=20` for that provider/model

---

### Requirement: SessionUsageStats.begin_invocation resets current invocation
`SessionUsageStats.begin_invocation()` SHALL call `_current_invocation.zero()` to clear per-request statistics. `_lifecycle_total` SHALL remain unchanged.

#### Scenario: begin_invocation clears current but preserves lifecycle
- **WHEN** `add_stats` has been called and then `begin_invocation()` is called
- **THEN** `_current_invocation` is empty (falsy) and `_lifecycle_total` still contains the accumulated data

#### Scenario: begin_invocation on fresh instance is a no-op
- **WHEN** `begin_invocation()` is called on a newly constructed `SessionUsageStats`
- **THEN** no exception is raised and both members remain empty

---

### Requirement: SessionUsageStats properties for data access
`SessionUsageStats` SHALL expose the following properties:
- `current_invocation_data` → returns `_current_invocation.data` (type `dict[str, dict[str, ModelStats]]`)
- `lifecycle_total_data` → returns `_lifecycle_total.data` (type `dict[str, dict[str, ModelStats]]`)

#### Scenario: current_invocation_data reflects per-request stats
- **WHEN** `add_stats` is called and then `current_invocation_data` is accessed
- **THEN** it returns the data dict from `_current_invocation`

#### Scenario: lifecycle_total_data reflects cumulative stats
- **WHEN** `add_stats` is called across multiple invocations
- **THEN** `lifecycle_total_data` contains the total accumulated data across all invocations

#### Scenario: current_invocation_data is empty after begin_invocation
- **WHEN** `begin_invocation()` is called
- **THEN** `current_invocation_data` returns an empty dict

---

### Requirement: SessionUsageStats satisfies UsageStats Protocol
`SessionUsageStats` SHALL structurally satisfy the `UsageStats` Protocol by implementing the `add_stats(provider, model, usage, cost=None)` method with a compatible signature. This allows `SessionUsageStats` to be used anywhere a `UsageStats` is expected.

#### Scenario: SessionUsageStats passes Protocol check
- **WHEN** a function parameter is typed as `UsageStats` and a `SessionUsageStats` instance is passed
- **THEN** mypy SHALL accept it without type errors (structural subtyping via Protocol)
