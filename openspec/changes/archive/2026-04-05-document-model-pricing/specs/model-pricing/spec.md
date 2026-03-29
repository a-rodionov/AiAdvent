## ADDED Requirements

### Requirement: ModelPricingDTO input model
`ModelPricingDTO` is a Pydantic `BaseModel` representing the pricing configuration for a single provider/model pair. It SHALL carry: `provider` (non-empty string), `model` (non-empty string), `tokens_per_price` (positive integer ≥ 1), `base_input_tokens` (float ≥ 0), and `output_tokens` (float ≥ 0). Empty `provider` or `model`, a `tokens_per_price` of 0, or negative price fields SHALL be rejected by Pydantic validation. Zero prices (free model) SHALL be accepted.

#### Scenario: valid DTO is constructed
- **WHEN** all fields are provided with valid values
- **THEN** a `ModelPricingDTO` instance is returned with fields accessible by name

#### Scenario: empty provider raises ValidationError
- **WHEN** `ModelPricingDTO` is constructed with `provider=""`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: empty model raises ValidationError
- **WHEN** `ModelPricingDTO` is constructed with `model=""`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: tokens_per_price of zero raises ValidationError
- **WHEN** `ModelPricingDTO` is constructed with `tokens_per_price=0`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: negative base_input_tokens raises ValidationError
- **WHEN** `ModelPricingDTO` is constructed with `base_input_tokens=-0.1`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: negative output_tokens raises ValidationError
- **WHEN** `ModelPricingDTO` is constructed with `output_tokens=-0.1`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: zero prices are accepted
- **WHEN** `ModelPricingDTO` is constructed with `base_input_tokens=0.0` and `output_tokens=0.0`
- **THEN** the DTO is created successfully with both price fields equal to `0.0`

---

### Requirement: PricingResult transient value object
`PricingResult` is an immutable `NamedTuple` with three float fields: `base_input_tokens_cost`, `output_tokens_cost`, and `total_cost`. It is the return type of `ModelPricing.estimate()` and is never persisted. Fields are accessible both by name and by positional index.

#### Scenario: fields are accessible by name
- **WHEN** a `PricingResult` is constructed with specific float values
- **THEN** `result.base_input_tokens_cost`, `result.output_tokens_cost`, and `result.total_cost` return the correct values

#### Scenario: fields are accessible by positional index
- **WHEN** a `PricingResult` is constructed
- **THEN** `result[0]`, `result[1]`, `result[2]` return `base_input_tokens_cost`, `output_tokens_cost`, and `total_cost` respectively

---

### Requirement: TokensCost accumulated cost model
`TokensCost` is a Pydantic `BaseModel` representing accumulated monetary cost in currency units. It SHALL carry: `prompt_tokens` (float, default `0.0`, ≥ 0), `completion_tokens` (float, default `0.0`, ≥ 0), and `total_tokens` (float, default `0.0`, ≥ 0). Negative values for any field SHALL be rejected by Pydantic validation. It is stored persistently inside `UsageStatistics` within `SessionDto`.

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

### Requirement: UsageStatistics compound statistics model
`UsageStatistics` is a Pydantic `BaseModel` pairing token counts with optional cost data. It SHALL carry: `tokens_usage` (a `TokensUsage` instance with `prompt_tokens` and `completion_tokens` counts) and `tokens_cost` (an optional `TokensCost`, defaults to `None`). When no pricing is configured for a provider/model, `tokens_cost` SHALL remain `None`.

#### Scenario: tokens_cost defaults to None
- **WHEN** `UsageStatistics` is constructed with only `tokens_usage`
- **THEN** `usage.tokens_cost` is `None`

#### Scenario: tokens_cost is set when provided
- **WHEN** `UsageStatistics` is constructed with both `tokens_usage` and a `TokensCost`
- **THEN** `usage.tokens_cost` is the provided `TokensCost` instance and `total_tokens` is accessible

---

### Requirement: ModelPricing engine construction
`ModelPricing` is the runtime pricing engine. It SHALL be constructed from a non-empty list of `ModelPricingDTO`s. An empty list SHALL raise `ValueError` with a message containing "must not be empty". The class method `from_dtos(dtos)` is an alias for the constructor. Internally it builds a lookup keyed by `(provider, model)` tuples.

#### Scenario: empty DTO list raises ValueError
- **WHEN** `ModelPricing([])` is called
- **THEN** `ValueError` is raised with a message containing "must not be empty"

#### Scenario: from_dtos classmethod constructs ModelPricing
- **WHEN** `ModelPricing.from_dtos([dto])` is called with a valid DTO list
- **THEN** a `ModelPricing` instance is returned

---

### Requirement: ModelPricing.estimate cost calculation
`ModelPricing.estimate(*, provider, model, base_input_tokens, output_tokens)` SHALL compute costs using the formula: `base_input_tokens_cost = base_input_tokens × base_input_price / tokens_per_price` and `output_tokens_cost = output_tokens × output_price / tokens_per_price`, with `total_cost = base_input_tokens_cost + output_tokens_cost`. It SHALL return a `PricingResult`. If the `(provider, model)` pair is not in the registry, it SHALL raise `KeyError`. Each provider/model pair is resolved independently from its own stored rates.

#### Scenario: estimate raises KeyError for unknown provider
- **WHEN** `estimate` is called with a provider not in the registry
- **THEN** `KeyError` is raised

#### Scenario: estimate raises KeyError for unknown model
- **WHEN** `estimate` is called with a known provider but unknown model
- **THEN** `KeyError` is raised

#### Scenario: estimate computes correct base input cost
- **WHEN** `estimate` is called with 1,000,000 input tokens at $3.0 per 1,000,000 tokens
- **THEN** `result.base_input_tokens_cost` is approximately `3.0`

#### Scenario: estimate computes correct output cost
- **WHEN** `estimate` is called with 1,000,000 output tokens at $15.0 per 1,000,000 tokens
- **THEN** `result.output_tokens_cost` is approximately `15.0`

#### Scenario: estimate computes correct total cost
- **WHEN** `estimate` is called with both input and output tokens
- **THEN** `result.total_cost` equals `base_input_tokens_cost + output_tokens_cost`

#### Scenario: estimate handles fractional token counts correctly
- **WHEN** `estimate` is called with token counts that produce a non-integer cost
- **THEN** the result costs are correct floating-point values

#### Scenario: estimate returns PricingResult instance
- **WHEN** `estimate` is called with a known provider/model
- **THEN** the return value is an instance of `PricingResult`

#### Scenario: multiple models resolved independently
- **WHEN** two different models are registered with different rates
- **THEN** `estimate` returns distinct costs for each model matching their respective rates
