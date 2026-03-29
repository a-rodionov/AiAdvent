## Why

`ILlmPort` is the primary hexagonal-architecture port that decouples the domain from any concrete LLM SDK, yet it currently has no documentation — no docstrings, no spec, and no usage guide. This makes it hard for contributors to understand how to use the interface, implement new adapters, or extend the event model.

## What Changes

- Add inline docstrings to `ILlmPort`, `acompletion`, and all `CompletionEvent` subclasses in `app/domain/interfaces/llm_port.py`
- Create a spec document describing the contract, event lifecycle, and usage patterns
- Document the `BillingEvent` inclusion rules and stream termination guarantee (`CompletionDoneEvent` always last)
- Document `CompletionConfig` fields that drive adapter behavior (provider, model, streaming preference, output schema)

## Capabilities

### New Capabilities

- `llm-port-contract`: Formal specification of the `ILlmPort` interface — method signature, streaming event sequence, termination guarantees, and error semantics for implementors and consumers

### Modified Capabilities

## Impact

- `app/domain/interfaces/llm_port.py` — docstrings added (no behavior changes)
- `openspec/specs/llm-port-contract/spec.md` — new spec file created
- No API changes, no breaking changes, no dependency changes
