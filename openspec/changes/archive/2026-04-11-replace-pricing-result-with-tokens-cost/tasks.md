## 1. Update tests (TDD — write failing tests first)

- [x] 1.1 In `tests/domain/value_objects/test_pricing.py`: remove the `TestPricingResult` class and its import of `PricingResult`
- [x] 1.2 In `tests/domain/value_objects/test_pricing.py`: update `TestModelBilling` estimate scenarios to assert `result.prompt_tokens`, `result.completion_tokens`, `result.total_tokens` (instead of `base_input_tokens_cost`, `output_tokens_cost`, `total_cost`)
- [x] 1.3 In `tests/domain/value_objects/test_pricing.py`: add scenario asserting `estimate()` returns a `TokensCost` instance (not `PricingResult`)
- [x] 1.4 Confirm tests fail with the current implementation before proceeding

## 2. Update implementation

- [x] 2.1 In `server/application/domain/model/model_billing.py`: remove the `PricingResult` class and its `NamedTuple` import (if no longer needed)
- [x] 2.2 In `server/application/domain/model/model_billing.py`: change `ModelBilling.estimate()` return annotation from `PricingResult` to `TokensCost`
- [x] 2.3 In `server/application/domain/model/model_billing.py`: update `estimate()` body to return `TokensCost(prompt_tokens=..., completion_tokens=..., total_tokens=...)`

## 3. Verify

- [x] 3.1 Run `pytest tests/domain/value_objects/test_pricing.py` — all tests pass
- [x] 3.2 Run `pytest` — no regressions across the full test suite
- [x] 3.3 Run `mypy server/` — no type errors
