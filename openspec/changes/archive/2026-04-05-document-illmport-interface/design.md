## Context

`ILlmPort` is the domain-layer port (hexagonal architecture) through which all LLM completions flow. It resides in `server/domain/interfaces/llm_port.py` alongside its event value objects. The single concrete adapter is `LlmAdapter` in `server/adapters/gateways/llm_adapter.py`, which wraps the `any-llm` SDK.

Currently the file contains no docstrings, module-level documentation, or formal spec. Contributors must read adapter implementation code to understand the streaming event contract. The change is purely additive: inline documentation and a spec file.

## Goals / Non-Goals

**Goals:**

- Add docstrings to `ILlmPort`, `acompletion`, and all `CompletionEvent` subclasses
- Specify the guaranteed event ordering (stream always ends with `CompletionDoneEvent`)
- Specify when `BillingEvent` is emitted and whether it is mandatory
- Create `openspec/specs/llm-port-contract/spec.md` as the machine-readable source of truth
- Ensure mypy type correctness is preserved (no signature changes)

**Non-Goals:**

- Changing the interface signature or adding new methods
- Adding a new adapter or modifying `LlmAdapter`
- Documenting `CompletionConfig` or `TokensUsage` in depth (separate concern)
- Adding runtime validation or defensive assertions to the port

## Decisions

### Docstring style: Google-style docstrings

**Rationale**: The project uses ruff for linting; Google-style is the de-facto standard for Python projects and supported natively by mkdocs/sphinx. Alternatives (NumPy, reStructuredText) add heavier syntax overhead for a simple interface.

### Spec lives in `openspec/specs/llm-port-contract/spec.md`

**Rationale**: Follows existing spec layout (`session`, `model-pricing`, `message-context-strategy`). A new capability folder makes the spec findable and independently archivable. Alternative of embedding spec content in the design doc would reduce discoverability.

### Event ordering contract expressed as SHALL requirements

**Rationale**: The streaming protocol has an implicit invariant — `CompletionDoneEvent` must be the last event, and `BillingEvent` (if present) precedes it. Making this explicit prevents broken adapter implementations. This is documented in both the spec and the `acompletion` docstring.

### No changes to `__init__.py` re-exports

**Rationale**: Consumers already import directly from `server.domain.interfaces.llm_port`. Adding re-exports would change the public API surface without clear benefit.

## Risks / Trade-offs

- **Docstrings becoming stale** → Mitigated by keeping docstrings tightly scoped to the interface contract (not implementation details), which changes less often.
- **Spec diverging from code** → Mitigated by making the spec normative and task-linking it to the interface file so future changes update both.

## Migration Plan

No migration needed. This is a documentation-only change with no runtime behavior modifications. Deploy by merging the PR; no rollback required.
