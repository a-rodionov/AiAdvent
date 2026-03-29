## MODIFIED Requirements

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
