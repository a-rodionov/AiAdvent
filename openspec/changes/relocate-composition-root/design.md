## Context

The `server/common/` package is meant to hold pure, layer-independent utilities. Currently it contains `app_factory.py` (composition root importing adapters + services + FastAPI) and `config_loader.py` (imports domain model types). Both violate `common/`'s independence contract. The project's architecture defines an infrastructure layer for "framework wiring, config loading, server factory" — these files belong there.

## Goals / Non-Goals

**Goals:**

- Move `app_factory.py` and `config_loader.py` out of `common/` to restore its independence
- Place them in the infrastructure layer (root of `server/` package, alongside `server.py`)
- Update all import references

**Non-Goals:**

- Refactoring `app_factory.py` or `config_loader.py` internals
- Creating a new `infrastructure/` sub-package (not justified for two files)
- Changing `json_helpers.py` (it stays in `common/`)

## Decisions

### Decision 1: Move to `server/` root, not a new `infrastructure/` package

Place `app_factory.py` and `config_loader.py` directly in `server/` alongside `server.py`.

**Rationale:** `server.py` is already the entry point at this level and performs infrastructure duties. Adding two more infrastructure files here is natural. A dedicated `infrastructure/` package would be over-engineering for three files total.

**Alternative considered:** Create `server/infrastructure/` sub-package. Rejected — adds a directory for only two files, with no clear benefit until the infrastructure layer grows.

### Decision 2: Keep `common/` with `json_helpers.py` only

After the move, `common/` contains only `json_helpers.py` and `__init__.py`. This is fine — it may grow again with genuinely layer-independent utilities.

**Alternative considered:** Remove `common/` entirely and move `json_helpers.py` to `server/`. Rejected — keeping the package preserves a clear home for future shared utilities.

## Risks / Trade-offs

- **[Risk] Missed import update** → Use grep to find all references to `server.common.app_factory` and `server.common.config_loader` before and after the move.
- **[Risk] `common/` feels sparse with one file** → Acceptable; the package has a clear purpose and can grow naturally.
