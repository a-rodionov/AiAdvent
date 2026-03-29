## Purpose

The `usage-stats` capability provides lightweight value objects for accumulating per-model token usage and optional cost data across LLM requests within a session. It replaces the former `UsageStatistics` Pydantic model with `ModelStats` (a `NamedTuple`) and `UsageStats` (a mutable accumulator), removing circular-import issues and keeping accumulation logic encapsulated.

## Requirements

### Requirement: ModelStats entry type

`ModelStats` SHALL be a `NamedTuple` with two fields: `usage: TokensUsage` and `cost: TokensCost | None`, where `cost` defaults to `None`. It is the value type stored per provider/model pair inside `UsageStats`.

#### Scenario: fields accessible by name

- **WHEN** `ModelStats` is constructed with a `TokensUsage` and a `TokensCost`
- **THEN** `.usage` returns the `TokensUsage` and `.cost` returns the `TokensCost`

#### Scenario: cost defaults to None

- **WHEN** `ModelStats` is constructed with only `usage`
- **THEN** `.cost` is `None`

---

### Requirement: UsageStats is a Protocol

`UsageStats` SHALL be a `typing.Protocol` defining the interface for token usage accumulation. It SHALL declare the method `add_stats(provider: str, model: str, usage: TokensUsage, cost: TokensCost | None = None) -> None`. Classes satisfying this protocol can be used interchangeably — specifically, `SessionUsageStats` satisfies `UsageStats` structurally.

The concrete `UsageStats` class (the current mutable accumulator) SHALL continue to exist and implement this protocol. Its construction, `zero()`, `add_stats()`, `data` property, and truthiness behavior remain unchanged.

#### Scenario: UsageStats is a Protocol

- **WHEN** a developer inspects `UsageStats` in `server/domain/value_objects/usage_stats.py`
- **THEN** it inherits from `typing.Protocol`

#### Scenario: concrete UsageStats still works as before

- **WHEN** `UsageStats()` is constructed and `add_stats` is called
- **THEN** it accumulates stats identically to the current behavior

#### Scenario: SessionUsageStats satisfies UsageStats Protocol

- **WHEN** a `SessionUsageStats` instance is passed to a function typed as `UsageStats`
- **THEN** mypy accepts it without type errors

---

### Requirement: UsageStats construction

`UsageStats` SHALL be constructable with no arguments (empty accumulator) or with an optional `data: dict[str, dict[str, ModelStats]]` argument that pre-populates its internal state. The internal member `_data` SHALL have type `dict[str, dict[str, ModelStats]]` keyed by provider (outer) and model (inner).

#### Scenario: default construction yields empty accumulator

- **WHEN** `UsageStats()` is called with no arguments
- **THEN** `bool(usage_stats)` is `False`

#### Scenario: construction with data pre-populates state

- **WHEN** `UsageStats(data={"anthropic": {"claude-3": ModelStats(usage=TokensUsage())}})` is called
- **THEN** `bool(usage_stats)` is `True` and `usage_stats.data["anthropic"]["claude-3"]` is accessible

---

### Requirement: UsageStats.zero clears state

`UsageStats.zero()` SHALL remove all entries from the internal dict, leaving the accumulator empty.

#### Scenario: zero on populated accumulator clears it

- **WHEN** `add_stats` has been called at least once and then `zero()` is called
- **THEN** `bool(usage_stats)` is `False`

#### Scenario: zero on empty accumulator is a no-op

- **WHEN** `zero()` is called on a freshly constructed `UsageStats`
- **THEN** no exception is raised and `bool(usage_stats)` remains `False`

---

### Requirement: UsageStats.add_stats accumulates usage and optional cost

`UsageStats.add_stats(provider, model, usage, cost=None)` SHALL update the internal dict at `_data[provider][model]`. On first call for a `(provider, model)` pair it SHALL create a new `ModelStats` entry with the supplied `usage` and `cost`. On subsequent calls for the same pair it SHALL add `usage.prompt_tokens` and `usage.completion_tokens` to the existing totals. Cost accumulation SHALL follow: if either the stored cost or the new cost is non-`None`, both are treated as zero for missing fields and their values summed into a new `TokensCost`; if both are `None`, the stored cost remains `None`.

#### Scenario: first call creates entry

- **WHEN** `add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10, completion_tokens=5))` is called
- **THEN** `data["openai"]["gpt-4"].usage.prompt_tokens` is `10` and `.completion_tokens` is `5`

#### Scenario: second call accumulates token counts

- **WHEN** `add_stats` is called twice for the same provider/model with `prompt_tokens=10` each time
- **THEN** `data[provider][model].usage.prompt_tokens` is `20`

#### Scenario: cost accumulates when both calls provide cost

- **WHEN** `add_stats` is called twice with `cost=TokensCost(prompt_tokens=1.5, ...)` each time
- **THEN** `data[provider][model].cost.prompt_tokens` is `3.0`

#### Scenario: cost remains None when both calls pass cost=None

- **WHEN** `add_stats` is called twice without providing `cost`
- **THEN** `data[provider][model].cost` is `None`

#### Scenario: cost becomes non-None if second call provides cost

- **WHEN** first `add_stats` call omits `cost` and second call provides a `TokensCost`
- **THEN** `data[provider][model].cost` is non-`None` with values from the second call only

#### Scenario: different provider/model pairs tracked independently

- **WHEN** `add_stats` is called for `("anthropic", "claude-3")` and `("openai", "gpt-4")`
- **THEN** each pair has an independent entry in `_data`

---

### Requirement: UsageStats truthiness

`bool(UsageStats)` SHALL return `False` when `_data` is empty and `True` when at least one entry exists.

#### Scenario: empty accumulator is falsy

- **WHEN** `UsageStats()` is constructed
- **THEN** `bool(usage_stats)` is `False`

#### Scenario: non-empty accumulator is truthy

- **WHEN** at least one `add_stats` call has been made
- **THEN** `bool(usage_stats)` is `True`

---

### Requirement: UsageStats.data property

`UsageStats.data` SHALL return the internal `_data` dict (`dict[str, dict[str, ModelStats]]`) directly, without copying. It is the authoritative read interface for DTO serialization.

#### Scenario: data reflects current accumulator state

- **WHEN** `add_stats("p", "m", usage)` is called and then `data` is accessed
- **THEN** `data["p"]["m"]` is the `ModelStats` entry for that pair

---

### Requirement: TokensUsage defined in usage-stats module
The usage-stats module SHALL define the `TokensUsage` model, representing raw token counts (`prompt_tokens`, `completion_tokens`) for a single completion. Code that needs `TokensUsage` SHALL import it from the usage-stats module, not from the completion module.

#### Scenario: TokensUsage accessible from usage-stats module
- **WHEN** a consumer imports `TokensUsage`
- **THEN** it SHALL import from `server.application.domain.model.usage_stats`
