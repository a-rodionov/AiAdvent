## ADDED Requirements

### Requirement: IModelBillingFactory port interface
`IModelBillingFactory` SHALL be a Protocol in the domain layer defining a single method `create(provider: str, model: str) -> ModelBilling | None`. It serves as a factory port for creating `ModelBilling` instances based on provider and model identifiers.

#### Scenario: create returns ModelBilling for known pair
- **WHEN** `factory.create(provider="anthropic", model="claude-3")` is called and pricing data exists for this pair
- **THEN** a `ModelBilling` instance configured with the correct rates is returned

#### Scenario: create returns None for unknown pair
- **WHEN** `factory.create(provider="unknown", model="no-model")` is called and no pricing data exists
- **THEN** `None` is returned

---

### Requirement: ModelBillingFactoryAdapter reads and caches pricing file
`ModelBillingFactoryAdapter` SHALL implement the `IModelBillingFactory` Protocol. Its constructor SHALL accept a `file_path: str` parameter, read and parse the JSON pricing file into a list of `ModelPricingDTO` objects, and cache them in memory as a `dict[(str, str), ModelPricingDTO]` keyed by `(provider, model)`. File reading and JSON parsing errors SHALL raise the same exceptions as the current `ModelPricingFileAdapter` (`FileNotFoundError`, `PermissionError`, `ValueError`).

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
When `create(provider, model)` is called, the adapter SHALL look up `(provider, model)` in its cached dict. If found, it SHALL extract `tokens_per_price`, `base_input_tokens`, and `output_tokens` from the matching `ModelPricingDTO` and construct a `ModelBilling` instance with those raw parameters. If not found, it SHALL return `None`.

#### Scenario: known pair returns configured ModelBilling
- **WHEN** `create("anthropic", "claude-3")` is called and a matching DTO exists with `tokens_per_price=1_000_000`, `base_input_tokens=3.0`, `output_tokens=15.0`
- **THEN** a `ModelBilling` is returned that computes costs using those rates

#### Scenario: unknown pair returns None
- **WHEN** `create("nonexistent", "model")` is called
- **THEN** `None` is returned
