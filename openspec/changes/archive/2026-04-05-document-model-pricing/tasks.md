## 1. Verify spec completeness

- [x] 1.1 Read `specs/model-pricing/spec.md` and confirm all five types are covered: `ModelPricingDTO`, `PricingResult`, `TokensCost`, `UsageStatistics`, and `ModelPricing`
- [x] 1.2 Cross-check each scenario against `tests/domain/value_objects/test_pricing.py` to confirm every test case has a matching scenario in the spec
- [x] 1.3 Verify the cost formula (`cost = token_count × rate / tokens_per_price`) appears verbatim in the `ModelPricing.estimate` requirement

## 2. Register spec in project-wide index

- [x] 2.1 Copy `specs/model-pricing/spec.md` to `openspec/specs/model-pricing/spec.md`
- [x] 2.2 Confirm `openspec status` reflects the new spec as a recognised capability

## 3. Add inline docstrings to source

- [x] 3.1 Add a module-level docstring to `app/domain/value_objects/pricing.py` referencing the spec location and noting the circular-import shim for `TokensUsage`
- [x] 3.2 Add a one-line docstring to `ModelPricing.__init__` noting the `(provider, model)` tuple lookup structure
- [x] 3.3 Add a one-line docstring to `ModelPricing.estimate` stating the formula and the `KeyError` exception contract

## 4. Review and close

- [x] 4.1 Review design open question: decide whether `estimate()` should raise `ValueError` instead of `KeyError` for unknown models; update spec if behaviour changes
- [x] 4.2 Mark change complete once spec is in `openspec/specs/`, all docstrings added, and scenarios verified against tests
