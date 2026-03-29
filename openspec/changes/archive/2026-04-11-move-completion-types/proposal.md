## Why

`StopReason` and `TokensUsage` are defined in `completion.py` alongside `CompletionConfig`, but they are conceptually owned by different domains: `StopReason` belongs to session termination logic and `TokensUsage` belongs to usage statistics tracking. Keeping all three in `completion.py` creates artificial coupling and forces unrelated modules (`session.py`, `usage_stats.py`) to import from the completion module.

## What Changes

- Move `StopReason` enum from `completion.py` to `session.py`
- Move `TokensUsage` model from `completion.py` to `usage_stats.py`
- Update all import sites across the codebase (`llm_port.py`, `ws_protocol.py`, `ws_handler.py`, `session.py`, `usage_stats.py`, `completion.py` itself) to import from the new locations

## Capabilities

### New Capabilities
<!-- None — this is a pure refactor with no new behavior -->

### Modified Capabilities
- `session`: `StopReason` enum moves into this module; no requirement changes, internal reorganization only
- `usage-stats`: `TokensUsage` model moves into this module; no requirement changes, internal reorganization only

## Impact

- **Files modified**: `completion.py`, `session.py`, `usage_stats.py`, `llm_port.py`, `ws_protocol.py`, `ws_handler.py`
- **No API or behavior changes** — purely a module reorganization
- **No breaking changes to external interfaces**
