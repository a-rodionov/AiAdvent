## Context

`ModelBillingFactoryAdapter` is currently located at `server/adapter/outbound/llm/model_billing_factory_adapter.py`. It reads a JSON pricing file from disk and constructs `ModelBilling` instances from the cached data. Its only I/O is filesystem access — it has no LLM SDK dependency and does not communicate with any LLM provider.

The `llm/` package is reserved for adapters that wrap LLM provider SDKs (e.g., `llm_adapter.py`, `llm_port_factory_adapter.py`). Placing a file-reading adapter there violates the principle of grouping adapters by their external concern.

## Goals / Non-Goals

**Goals:**
- Relocate `ModelBillingFactoryAdapter` to `server/adapter/outbound/persistence/` where file-based adapters live
- Update all import sites to use the new path
- Keep the `persistence` package's `__init__.py` consistent

**Non-Goals:**
- Changing any logic, interface, or behaviour of `ModelBillingFactoryAdapter`
- Renaming the class or any of its methods
- Modifying tests beyond updating import paths

## Decisions

**Move file, do not copy**: Delete from `llm/` and create in `persistence/`. No compatibility shim or re-export in the old location — the old path will simply not exist. All callers must update their imports.

**Rationale**: A re-export shim would hide the misclassification and let stale imports linger. A clean cut forces all call sites to acknowledge the correct location.

## Risks / Trade-offs

- [Import breakage at runtime] → Mitigated by grepping all import sites before the move and updating them atomically in the same commit.
- [Test failures] → Tests that import from the old path will fail immediately and visibly, which is the intended signal.
