## REMOVED Requirements

### Requirement: PricingResult transient value object

**Reason**: `PricingResult` is a redundant NamedTuple that duplicates `TokensCost` with different field names. `ModelBilling.estimate()` now returns `TokensCost` directly, eliminating the need for a separate result type.
**Migration**: Replace any reference to `PricingResult` fields (`base_input_tokens_cost`, `output_tokens_cost`, `total_cost`) with the corresponding `TokensCost` fields (`prompt_tokens`, `completion_tokens`, `total_tokens`). Remove any import of `PricingResult` from `server.application.domain.model.model_billing`.

---

## MODIFIED Requirements

### Requirement: ModelBilling.estimate cost calculation

`ModelBilling.estimate(*, base_input_tokens: int, output_tokens: int)` SHALL compute costs using the formula: `prompt_tokens_cost = base_input_tokens * self._base_input_tokens / self._tokens_per_price` and `completion_tokens_cost = output_tokens * self._output_tokens / self._tokens_per_price`, with `total_tokens_cost = prompt_tokens_cost + completion_tokens_cost`. It SHALL return a `TokensCost` instance with `prompt_tokens=prompt_tokens_cost`, `completion_tokens=completion_tokens_cost`, and `total_tokens=total_tokens_cost`. The method SHALL NOT accept `provider` or `model` parameters — the `ModelBilling` instance is already scoped to a specific provider/model pair by the factory.

#### Scenario: estimate computes correct prompt (input) cost

- **WHEN** `estimate(base_input_tokens=1_000_000, output_tokens=0)` is called with rates `tokens_per_price=1_000_000, base_input_tokens=3.0`
- **THEN** `result.prompt_tokens` is `3.0`

#### Scenario: estimate computes correct completion (output) cost

- **WHEN** `estimate(base_input_tokens=0, output_tokens=1_000_000)` is called with rates `tokens_per_price=1_000_000, output_tokens=15.0`
- **THEN** `result.completion_tokens` is `15.0`

#### Scenario: estimate computes correct total cost

- **WHEN** `estimate` is called with both input and output tokens
- **THEN** `result.total_tokens` equals `result.prompt_tokens + result.completion_tokens`

#### Scenario: estimate returns TokensCost instance

- **WHEN** `estimate` is called
- **THEN** the return value is an instance of `TokensCost`
