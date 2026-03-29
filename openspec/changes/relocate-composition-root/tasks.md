## 1. Move files

- [ ] 1.1 Move `server/common/app_factory.py` to `server/app_factory.py`
- [ ] 1.2 Move `server/common/config_loader.py` to `server/config_loader.py`
- [ ] 1.3 Remove old imports/re-exports from `server/common/__init__.py` if any

## 2. Update imports

- [ ] 2.1 Update `server/server.py` — change `server.common.config_loader` to `server.config_loader` and `server.common.app_factory` to `server.app_factory`
- [ ] 2.2 Grep for any remaining references to `server.common.app_factory` or `server.common.config_loader` and update them

## 3. Verify

- [ ] 3.1 Run full test suite and confirm all tests pass
- [ ] 3.2 Run mypy and confirm no type errors
