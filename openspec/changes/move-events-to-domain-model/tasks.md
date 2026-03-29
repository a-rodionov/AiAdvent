## 1. Create domain event module

- [ ] 1.1 Create `server/application/domain/model/llm_events.py` with `CompletionEvent`, `TextChunkEvent`, `CompletionDoneEvent` (move from `port/outbound/llm_port.py`)
- [ ] 1.2 Export new event types from `server/application/domain/model/__init__.py`

## 2. Update port to import from domain model

- [ ] 2.1 Remove event class definitions from `server/application/port/outbound/llm_port.py`
- [ ] 2.2 Add imports of event types from `server.application.domain.model.llm_events` into `llm_port.py` and re-export them

## 3. Fix domain model imports

- [ ] 3.1 Update `server/application/domain/model/session.py` — import events from `llm_events` instead of `port/outbound/llm_port`
- [ ] 3.2 Update `server/application/domain/model/llm_stats_decorator.py` — import events from `llm_events` instead of `port/outbound/llm_port`
- [ ] 3.3 Update `server/application/domain/model/context_strategy.py` — import events from `llm_events` instead of `port/outbound/llm_port`

## 4. Update tests

- [ ] 4.1 Update test imports that reference event types from `port/outbound/llm_port` to use `domain/model/llm_events`
- [ ] 4.2 Add test verifying no file under `domain/model/` imports from `server.application.port`

## 5. Verify

- [ ] 5.1 Run full test suite and confirm all tests pass
- [ ] 5.2 Run mypy and confirm no type errors
