## 1. Relocate the adapter module

- [x] 1.1 Copy `server/adapter/outbound/llm/model_billing_factory_adapter.py` to `server/adapter/outbound/persistence/model_billing_factory_adapter.py`
- [x] 1.2 Delete `server/adapter/outbound/llm/model_billing_factory_adapter.py`

## 2. Update import sites

- [x] 2.1 Update `server/common/app_factory.py`: change import from `server.adapter.outbound.llm.model_billing_factory_adapter` to `server.adapter.outbound.persistence.model_billing_factory_adapter`
- [x] 2.2 Update `tests/adapter/test_model_billing_factory_adapter.py`: change import from `server.adapter.outbound.llm.model_billing_factory_adapter` to `server.adapter.outbound.persistence.model_billing_factory_adapter`

## 3. Verify

- [x] 3.1 Run `python -m pytest tests/adapter/test_model_billing_factory_adapter.py` and confirm all tests pass
- [x] 3.2 Run `python -m mypy server/` and confirm no type errors related to the move
