## 1. Protocol Conversions and UsageStats Refactoring

- [x] 1.1 Change `ILlmPort` base class from `ABC` to `Protocol` in `app/domain/interfaces/llm_port.py`. Remove `@abstractmethod` decorator. Remove `abc` import. Add `typing.Protocol` import. Write tests verifying structural subtyping works.
- [x] 1.2 Change `UsageStats` to a `Protocol` in `app/domain/value_objects/usage_stats.py`. Create a separate concrete `UsageStatsAccumulator` class (or keep the existing class name and add a separate Protocol). Ensure existing tests pass. Write test verifying `SessionUsageStats` satisfies the Protocol.
- [x] 1.3 Remove `BillingEvent` class from `app/domain/interfaces/llm_port.py`. Update event ordering docstring on `acompletion` to remove `BillingEvent` reference.

## 2. ModelBilling Refactoring

- [x] 2.1 Rename `app/domain/value_objects/pricing.py` to `app/domain/value_objects/model_billing.py`. Rename `ModelPricing` class to `ModelBilling`. Change constructor to accept raw parameters (`tokens_per_price`, `base_input_tokens`, `output_tokens`) instead of `list[ModelPricingDTO]`. Remove `from_dtos` classmethod. Update `estimate` to remove `provider`/`model` parameters (use stored rates directly). Write TDD tests for `ModelBilling` construction and estimation.
- [x] 2.2 Update all imports across the codebase from `pricing` to `model_billing` and from `ModelPricing` to `ModelBilling`. Move `ModelPricingDTO`, `PricingResult`, `TokensCost` to remain in `model_billing.py`.

## 3. SessionUsageStats

- [x] 3.1 Create `SessionUsageStats` class in `app/domain/value_objects/usage_stats.py` (or a new file). Implement constructor with optional `data` parameter, `add_stats` method delegating to both `_current_invocation` and `_lifecycle_total`, `begin_invocation` method, and `current_invocation_data`/`lifecycle_total_data` properties. Write TDD tests per spec scenarios.

## 4. LlmStatsDecorator

- [x] 4.1 Create `LlmStatsDecorator` class in domain layer (e.g., `app/domain/entities/llm_stats_decorator.py` or `app/domain/interfaces/llm_stats_decorator.py`). Implement constructor accepting `ILlmPort`, `SessionUsageStats`, optional `ModelBilling`. Implement `acompletion` that passes through `TextChunkEvent`, intercepts `CompletionDoneEvent` for stats accumulation. Write TDD tests per spec scenarios.
- [x] 4.2 Write test for `KeyError` handling when `ModelBilling.estimate()` raises for unknown model — verify fallback to `cost=None`.

## 5. Factory Ports and Adapters

- [x] 5.1 Create `IModelBillingFactory` Protocol in domain layer (e.g., `app/domain/interfaces/model_billing_factory.py`). Define `create(provider, model) -> ModelBilling | None`.
- [x] 5.2 Create `ModelBillingFactoryAdapter` in adapters layer (e.g., `app/adapters/gateways/model_billing_factory_adapter.py`). Read pricing file, cache DTOs, implement `create` that constructs `ModelBilling` from raw DTO parameters or returns `None`.
- [x] 5.3 Create `ILlmPortFactory` Protocol in domain layer (e.g., `app/domain/interfaces/llm_port_factory.py`). Define `create(session_id, completion_config) -> ILlmPort`.
- [x] 5.4 Create `LlmPortFactoryAdapter` in adapters layer (e.g., `app/adapters/gateways/llm_port_factory_adapter.py`). Implement nested dict cache `{session_id: {provider: LlmAdapter}}`. Write tests for caching behavior.

## 6. Session Refactoring

- [x] 6.1 Refactor `Session.__init__` to accept new parameters: `billing`, `strategy_type`, `strategy_metadata`, `strategy_records`, `strategy_llm`, `strategy_completion_config`, `strategy_billing`. Create `SessionUsageStats`, two `LlmStatsDecorator` instances, and build strategy internally. Remove `_handle_token_usage`, `_request_statistics`. Write TDD tests.
- [x] 6.2 Update `Session.create` classmethod to match new constructor signature. Write tests.
- [x] 6.3 Update `Session.from_dto` classmethod to accept `billing`, `strategy_llm`, `strategy_billing` parameters. Write tests.
- [x] 6.4 Update `Session.to_dto` to use `_usage_stats.lifecycle_total_data`. Write tests.
- [x] 6.5 Refactor `Session.acompletion` to: call `_usage_stats.begin_invocation()`, use `_llm_stats` instead of `_llm`, remove `BillingEvent` handling, use `_usage_stats.current_invocation_data` for done event statistics. Write TDD tests.
- [x] 6.6 Update `Session.statistics` property to return `SessionUsageStats`. Update `SessionCompletionDoneEvent` consumers if needed.

## 7. MessageContextStrategy Cleanup

- [x] 7.1 Remove `TokenUsageHandler` type alias, `OnTokenUsage()` method, `_emit_token_usage()` method, and `_token_usage_handlers` member from `MessageContextStrategy` base class.
- [x] 7.2 Simplify `SummaryStrategy._apply_strategy`: remove `BillingEvent` handling and `_emit_token_usage` calls. The strategy's `_llm` (a `LlmStatsDecorator`) handles stats transparently.
- [x] 7.3 Update existing `MessageContextStrategy` tests to remove token usage handler assertions. Add tests verifying no token handler mechanism exists.

## 8. Use Cases and Wiring

- [x] 8.1 Update `CreateSessionUseCase` to use `ILlmPortFactory` and `IModelBillingFactory`. Create `ModelBilling` objects for session and strategy. Pass new parameters to `Session.create`. Write tests.
- [x] 8.2 Update `GetSessionUseCase` to use `ILlmPortFactory` and `IModelBillingFactory`. Pass `billing`, `strategy_llm`, `strategy_billing` to `Session.from_dto`. Write tests.
- [x] 8.3 Update `app/infrastructure/app_factory.py` to wire `LlmPortFactoryAdapter` and `ModelBillingFactoryAdapter`. Pass factories to use cases. Remove old `ModelPricingFileAdapter` usage.

## 9. Cleanup and Verification

- [x] 9.1 Remove `ModelPricingFileAdapter` from `app/adapters/gateways/pricing_file_adapter.py` (replaced by `ModelBillingFactoryAdapter`).
- [x] 9.2 Run full test suite. Fix any remaining import errors or test failures.
- [x] 9.3 Run mypy type checking. Fix any type errors from Protocol changes.
- [x] 9.4 Run ruff linter. Fix any lint issues.
