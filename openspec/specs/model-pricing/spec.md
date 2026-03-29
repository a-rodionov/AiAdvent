## ADDED Requirements

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

---

### Requirement: ModelBilling engine construction

`ModelBilling` (renamed from `ModelPricing`) is the runtime pricing engine. It SHALL be constructed from three raw parameters: `tokens_per_price` (int, ≥ 1), `base_input_tokens` (float, ≥ 0), and `output_tokens` (float, ≥ 0). It SHALL NOT accept `ModelCostDTO` or `list[ModelCostDTO]`. The `from_dtos` class method SHALL be removed. Internally it stores the three rate parameters for cost calculation.

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

---

### Requirement: File rename

- **FROM:** `server/domain/value_objects/pricing.py`
- **TO:** `server/domain/value_objects/model_billing.py`
