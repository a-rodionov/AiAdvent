## 1. Define inbound port protocols

- [ ] 1.1 Create `server/application/port/inbound/use_cases.py` with Protocol definitions for all 5 use cases
- [ ] 1.2 Export protocols from `server/application/port/inbound/__init__.py`

## 2. Update inbound adapters

- [ ] 2.1 Update `server/adapter/inbound/web/session_routes.py` — replace concrete use case type hints with inbound port protocols, remove service imports
- [ ] 2.2 Update `server/adapter/inbound/web/ws_handler.py` — replace concrete use case type hints with inbound port protocols, remove service imports

## 3. Tests

- [ ] 3.1 Add test verifying that each concrete use case class satisfies its corresponding inbound port protocol (mypy structural subtyping check)
- [ ] 3.2 Add test verifying no file under `server/adapter/inbound/` imports from `server.application.domain.service`

## 4. Verify

- [ ] 4.1 Run full test suite and confirm all tests pass
- [ ] 4.2 Run mypy and confirm no type errors
