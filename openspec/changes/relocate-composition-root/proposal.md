## Why

`server/common/` is defined as "pure Python reusable at any layer", but two of its files violate this:

- `app_factory.py` imports adapters, services, and FastAPI — it is the composition root, not a reusable utility.
- `config_loader.py` imports `CompletionConfig` from `application/domain/model/`, making `common/` depend on the application layer.

This breaks `common/`'s independence and muddies the architectural layering.

## What Changes

- **Move `app_factory.py`** from `server/common/` to `server/` (root of the server package, next to `server.py`). This is the composition root — it wires adapters to ports and belongs at the infrastructure level.
- **Move `config_loader.py`** from `server/common/` to `server/` for the same reason — it depends on domain model types and serves as infrastructure-level configuration.
- **Update all imports** referencing `server.common.app_factory` and `server.common.config_loader` to use the new paths.
- **`server/common/`** retains only truly independent utilities (`json_helpers.py`).

## Capabilities

### New Capabilities

_(none — internal refactoring)_

### Modified Capabilities

_(none — no spec-level behavior changes, only file locations)_

## Impact

- **Files moved**: `server/common/app_factory.py` → `server/app_factory.py`, `server/common/config_loader.py` → `server/config_loader.py`
- **Files updated**: `server/server.py` and any other file importing from `server.common.app_factory` or `server.common.config_loader`
- **No API or behavior changes**
