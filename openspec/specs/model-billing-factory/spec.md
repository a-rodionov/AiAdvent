## Purpose

TBD — This capability defines the `IModelBillingFactory` port interface and its `ModelBillingFactoryAdapter` infrastructure implementation for creating `ModelBilling` instances from pricing configuration files.

---

## Requirements

### Requirement: IModelBillingFactory port interface

`IModelBillingFactory` SHALL be a Protocol in the domain layer defining a single method `create(provider: str, model: str) -> ModelBilling | None`. It serves as a factory port for creating `ModelBilling` instances based on provider and model identifiers.

#### Scenario: create returns ModelBilling for known pair

- **WHEN** `factory.create(provider="anthropic", model="claude-3")` is called and pricing data exists for this pair
- **THEN** a `ModelBilling` instance configured with the correct rates is returned

#### Scenario: create returns None for unknown pair

- **WHEN** `factory.create(provider="unknown", model="no-model")` is called and no pricing data exists
- **THEN** `None` is returned

---

### Requirement: ModelCostDTO input model

`ModelCostDTO` is a Pydantic `BaseModel` representing the pricing configuration for a single provider/model pair. It SHALL carry: `provider` (non-empty string), `model` (non-empty string), `tokens_per_price` (positive integer ≥ 1), `base_input_tokens` (float ≥ 0), and `output_tokens` (float ≥ 0). Empty `provider` or `model`, a `tokens_per_price` of 0, or negative price fields SHALL be rejected by Pydantic validation. Zero prices (free model) SHALL be accepted.

#### Scenario: valid DTO is constructed

- **WHEN** all fields are provided with valid values
- **THEN** a `ModelCostDTO` instance is returned with fields accessible by name

#### Scenario: empty provider raises ValidationError

- **WHEN** `ModelCostDTO` is constructed with `provider=""`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: empty model raises ValidationError

- **WHEN** `ModelCostDTO` is constructed with `model=""`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: tokens_per_price of zero raises ValidationError

- **WHEN** `ModelCostDTO` is constructed with `tokens_per_price=0`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: negative base_input_tokens raises ValidationError

- **WHEN** `ModelCostDTO` is constructed with `base_input_tokens=-0.1`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: negative output_tokens raises ValidationError

- **WHEN** `ModelCostDTO` is constructed with `output_tokens=-0.1`
- **THEN** `pydantic.ValidationError` is raised

#### Scenario: zero prices are accepted

- **WHEN** `ModelCostDTO` is constructed with `base_input_tokens=0.0` and `output_tokens=0.0`
- **THEN** the DTO is created successfully with both price fields equal to `0.0`

---

### Requirement: ModelBillingFactoryAdapter reads and caches pricing file

`ModelBillingFactoryAdapter` SHALL implement the `IModelBillingFactory` Protocol. Its constructor SHALL accept a `file_path: str` parameter, read and parse the JSON pricing file into a list of `ModelCostDTO` objects, and cache them in memory as a `dict[(str, str), ModelCostDTO]` keyed by `(provider, model)`. File reading and JSON parsing errors SHALL raise the same exceptions as `ModelPricingFileAdapter` (`FileNotFoundError`, `PermissionError`, `ValueError`). The implementation SHALL reside in `server/adapter/outbound/persistence/model_billing_factory_adapter.py`.

#### Scenario: constructor reads and caches pricing data

- **WHEN** `ModelBillingFactoryAdapter("path/to/pricing.json")` is called with a valid file
- **THEN** all pricing entries are cached in memory

#### Scenario: file not found raises FileNotFoundError

- **WHEN** the file path does not exist
- **THEN** `FileNotFoundError` is raised

#### Scenario: invalid JSON raises ValueError

- **WHEN** the file contains invalid JSON
- **THEN** `ValueError` is raised

---

### Requirement: ModelBillingFactoryAdapter.create constructs ModelBilling from cached data

When `create(provider, model)` is called, the adapter SHALL look up `(provider, model)` in its cached dict. If found, it SHALL extract `tokens_per_price`, `base_input_tokens`, and `output_tokens` from the matching `ModelCostDTO` and construct a `ModelBilling` instance with those raw parameters. If not found, it SHALL return `None`.

#### Scenario: known pair returns configured ModelBilling

- **WHEN** `create("anthropic", "claude-3")` is called and a matching DTO exists with `tokens_per_price=1_000_000`, `base_input_tokens=3.0`, `output_tokens=15.0`
- **THEN** a `ModelBilling` is returned that computes costs using those rates

#### Scenario: unknown pair returns None

- **WHEN** `create("nonexistent", "model")` is called
- **THEN** `None` is returned
