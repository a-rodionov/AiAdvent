## Why

`ModelBillingFactoryAdapter` reads pricing data from a JSON file on disk — it is a persistence adapter, not an LLM adapter. Placing it under `server/adapter/outbound/llm/` misrepresents its responsibility and obscures the architectural boundary between LLM integration and file-based persistence.

## What Changes

- Move `server/adapter/outbound/llm/model_billing_factory_adapter.py` → `server/adapter/outbound/persistence/model_billing_factory_adapter.py`
- Update all import references to the new path
- Remove the file from the `llm` package and expose it from the `persistence` package

## Capabilities

### New Capabilities

_(none — this is a structural relocation, no new capabilities are introduced)_

### Modified Capabilities

- `model-billing-factory`: The `ModelBillingFactoryAdapter` implementation module path changes from `server.adapter.outbound.llm` to `server.adapter.outbound.persistence`. The contract (interface, behaviour, and tests) is unchanged.

## Impact

- `server/adapter/outbound/llm/model_billing_factory_adapter.py` — deleted
- `server/adapter/outbound/persistence/model_billing_factory_adapter.py` — created (same content)
- Any import of `server.adapter.outbound.llm.model_billing_factory_adapter` must be updated to `server.adapter.outbound.persistence.model_billing_factory_adapter`
- `server/adapter/outbound/llm/__init__.py` and `server/adapter/outbound/persistence/__init__.py` may need updating
