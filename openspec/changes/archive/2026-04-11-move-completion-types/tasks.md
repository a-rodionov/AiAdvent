## 1. Move StopReason to session.py

- [x] 1.1 Add `StopReason` enum definition to `session.py` (before the classes that use it)
- [x] 1.2 Remove `StopReason` definition from `completion.py`
- [x] 1.3 Remove `StopReason` import from `completion.py`'s imports in `session.py`
- [x] 1.4 Update `llm_port.py` to import `StopReason` from `server.application.domain.model.session`
- [x] 1.5 Update `ws_protocol.py` to import `StopReason` from `server.application.domain.model.session`
- [x] 1.6 Update `ws_handler.py` to import `StopReason` from `server.application.domain.model.session`

## 2. Move TokensUsage to usage_stats.py

- [x] 2.1 Add `TokensUsage` model definition to `usage_stats.py` (before the classes that use it)
- [x] 2.2 Remove `TokensUsage` definition from `completion.py`
- [x] 2.3 Remove `TokensUsage` import from `completion.py`'s imports in `usage_stats.py`
- [x] 2.4 Update `llm_port.py` to import `TokensUsage` from `server.application.domain.model.usage_stats`
- [x] 2.5 Update `ws_protocol.py` to import `TokensUsage` from `server.application.domain.model.usage_stats`

## 3. Verify

- [x] 3.1 Confirm no remaining imports of `StopReason` or `TokensUsage` from `completion.py` (grep check)
- [x] 3.2 Run `mypy` — no type errors
- [x] 3.3 Run tests — all pass
