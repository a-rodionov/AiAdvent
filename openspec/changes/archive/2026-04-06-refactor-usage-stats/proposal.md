## Why

Statistics accumulation is implemented as a standalone free function (`update_statistics`) operating on a raw `dict[str, UsageStatistics]` with fragile comma-joined string keys. Encapsulating this logic into a dedicated value object (`UsageStats`) gives the domain a first-class accumulator with a clear, testable API and removes the implicit coupling between `Session` internals and raw dict manipulation.

## What Changes

- **New** `UsageStats` value object in `app/domain/value_objects/usage_stats.py` with a `ModelStats` NamedTuple as its entry type
- **New** `ModelStats(NamedTuple)` holding `TokensUsage` and optional `TokensCost` — replaces `UsageStatistics`
- **Remove** `update_statistics()` free function from `session.py`
- **Remove** `UsageStatistics` Pydantic model from `pricing.py` (and its circular-import shim)
- `Session._statistics` and `Session._request_statistics` become `UsageStats` instances
- `Session._handle_token_usage` calls `UsageStats.add_stats()` instead of `update_statistics()`
- **BREAKING** `SessionDto.statistics` type changes from `dict[str, UsageStatistics]` to `dict[str, dict[str, ModelStats]]` (nested by provider then model)
- **BREAKING** `SessionCompletionDoneEvent.statistics` type changes to match
- No-billing-event path now passes `cost=None` to `add_stats` (previously passed zero-cost `TokensCost`); `tokens_cost` on the stored entry is `None` when no billing occurred

## Capabilities

### New Capabilities

- `usage-stats`: `UsageStats` value object encapsulating per-(provider, model) token and cost accumulation with `zero()`, `add_stats()`, `__bool__`, and a `data` property

### Modified Capabilities

- `session`: Statistics field type changes from flat string-keyed dict to nested provider→model dict; no-billing semantic changes from zero-cost to `None`
- `model-pricing`: `UsageStatistics` model removed; `TokensCost` remains

## Impact

- `app/domain/value_objects/usage_stats.py` — new file
- `app/domain/value_objects/pricing.py` — remove `UsageStatistics`
- `app/domain/entities/session.py` — `Session`, `SessionDto`, `SessionCompletionDoneEvent`
- `tests/domain/entities/test_session.py` — `TestUpdateStatistics` replaced by `TestUsageStats`; key access and no-billing assertion updated
