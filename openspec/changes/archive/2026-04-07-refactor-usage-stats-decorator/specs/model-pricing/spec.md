## MODIFIED Requirements

### Requirement: ModelBilling engine construction
`ModelBilling` (renamed from `ModelPricing`) is the runtime pricing engine. It SHALL be constructed from three raw parameters: `tokens_per_price` (int, ≥ 1), `base_input_tokens` (float, ≥ 0), and `output_tokens` (float, ≥ 0). It SHALL NOT accept `ModelPricingDTO` or `list[ModelPricingDTO]`. The `from_dtos` class method SHALL be removed. Internally it stores the three rate parameters for cost calculation.

#### Scenario: construction with raw parameters
- **WHEN** `ModelBilling(tokens_per_price=1_000_000, base_input_tokens=3.0, output_tokens=15.0)` is called
- **THEN** a `ModelBilling` instance is returned with the rates stored internally

#### Scenario: tokens_per_price of zero raises ValueError
- **WHEN** `ModelBilling(tokens_per_price=0, base_input_tokens=3.0, output_tokens=15.0)` is called
- **THEN** `ValueError` is raised

#### Scenario: negative base_input_tokens raises ValueError
- **WHEN** `ModelBilling(tokens_per_price=1_000_000, base_input_tokens=-1.0, output_tokens=15.0)` is called
- **THEN** `ValueError` is raised

---

### Requirement: ModelBilling.estimate cost calculation
`ModelBilling.estimate(*, base_input_tokens: int, output_tokens: int)` SHALL compute costs using the formula: `base_input_tokens_cost = base_input_tokens * self._base_input_tokens / self._tokens_per_price` and `output_tokens_cost = output_tokens * self._output_tokens / self._tokens_per_price`, with `total_cost = base_input_tokens_cost + output_tokens_cost`. It SHALL return a `PricingResult`. The method SHALL NOT accept `provider` or `model` parameters — the `ModelBilling` instance is already scoped to a specific provider/model pair by the factory.

#### Scenario: estimate computes correct base input cost
- **WHEN** `estimate(base_input_tokens=1_000_000, output_tokens=0)` is called with rates `tokens_per_price=1_000_000, base_input_tokens=3.0`
- **THEN** `result.base_input_tokens_cost` is `3.0`

#### Scenario: estimate computes correct output cost
- **WHEN** `estimate(base_input_tokens=0, output_tokens=1_000_000)` is called with rates `tokens_per_price=1_000_000, output_tokens=15.0`
- **THEN** `result.output_tokens_cost` is `15.0`

#### Scenario: estimate computes correct total cost
- **WHEN** `estimate` is called with both input and output tokens
- **THEN** `result.total_cost` equals `base_input_tokens_cost + output_tokens_cost`

#### Scenario: estimate returns PricingResult instance
- **WHEN** `estimate` is called
- **THEN** the return value is an instance of `PricingResult`

## RENAMED Requirements

### Requirement: ModelPricing engine construction
- **FROM:** `ModelPricing`
- **TO:** `ModelBilling`

### Requirement: ModelPricing.estimate cost calculation
- **FROM:** `ModelPricing.estimate`
- **TO:** `ModelBilling.estimate`

### Requirement: File rename
- **FROM:** `app/domain/value_objects/pricing.py`
- **TO:** `app/domain/value_objects/model_billing.py`
