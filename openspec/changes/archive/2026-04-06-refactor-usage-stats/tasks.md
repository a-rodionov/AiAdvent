## 1. UsageStats value object (TDD)

- [x] 1.1 Write failing tests for `ModelStats` NamedTuple: field access by name, `cost` defaults to `None`
- [x] 1.2 Write failing tests for `UsageStats` construction: empty (falsy), with `data` arg (truthy)
- [x] 1.3 Write failing tests for `UsageStats.zero()`: clears populated accumulator, no-op on empty
- [x] 1.4 Write failing tests for `UsageStats.add_stats()`: first call creates entry, second call accumulates tokens, cost accumulation (both non-None, both None, one None), independent pairs
- [x] 1.5 Write failing tests for `UsageStats.__bool__` and `UsageStats.data` property
- [x] 1.6 Create `app/domain/value_objects/usage_stats.py` with `ModelStats` and `UsageStats` to make all tests pass

## 2. Remove UsageStatistics from pricing.py

- [x] 2.1 Remove `UsageStatistics` class and its circular-import shim (`from app.domain.value_objects.completion import TokensUsage` + `UsageStatistics.model_rebuild()`) from `app/domain/value_objects/pricing.py`
- [x] 2.2 Update the `TokensCost` docstring/comment to remove reference to `UsageStatistics`
- [x] 2.3 Verify no other module imports `UsageStatistics` from `pricing.py`

## 3. Refactor Session aggregate (TDD)

- [x] 3.1 Write failing tests for updated `TestUsageStats` scenarios in `test_session.py`: replace `TestUpdateStatistics` class with `TestUsageStats` that tests `UsageStats.add_stats` directly with nested key access `["provider"]["model"]`
- [x] 3.2 Write failing test: no-billing completion results in `cost is None` (replaces `test_no_billing_event_total_cost_is_zero`)
- [x] 3.3 Write failing test: `session.statistics` starts falsy after `Session.create`
- [x] 3.4 Write failing test: `session.statistics` after two completions uses nested key access
- [x] 3.5 Remove `update_statistics()` free function from `app/domain/entities/session.py`
- [x] 3.6 Change `Session._statistics` and `Session._request_statistics` to `UsageStats` instances
- [x] 3.7 Replace `self._request_statistics = {}` in `acompletion` with `self._request_statistics.zero()`
- [x] 3.8 Rewrite `Session._handle_token_usage` to call `add_stats(provider, model, usage, cost)` on both `_statistics` and `_request_statistics`; pass `cost=None` when no `BillingEvent` was present
- [x] 3.9 Update `Session.to_dto`: set `statistics=self._statistics.data or None`
- [x] 3.10 Update `Session.from_dto`: reconstruct with `UsageStats(dto.statistics)`

## 4. Update SessionDto and SessionCompletionDoneEvent types

- [x] 4.1 Change `SessionDto.statistics` type annotation from `dict[str, UsageStatistics] | None` to `dict[str, dict[str, ModelStats]] | None`
- [x] 4.2 Change `SessionCompletionDoneEvent.statistics` type annotation to `dict[str, dict[str, ModelStats]] | None`
- [x] 4.3 Update imports in `session.py`: add `ModelStats`, `UsageStats` from `usage_stats`; remove `UsageStatistics` import from `pricing`

## 5. Sync delta specs and verify

- [x] 5.1 Run full test suite and confirm all tests pass
- [x] 5.2 Run `mypy` and `ruff` and fix any type or lint errors
