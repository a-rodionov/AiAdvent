## Why

The `MessageContextStrategy` interface is the core extension point for controlling how conversation history is managed and presented to the LLM, but it currently has no written specification — developers must read implementation code to understand the contract, the ordering guarantees, and the expected behaviour of each concrete strategy. Documenting it now will prevent misuse as the codebase grows and new strategies are added.

## What Changes

- Add a specification document for the `MessageContextStrategy` interface covering its purpose, lifecycle, and abstract method contracts.
- Document the three concrete strategies (`DummyStrategy`, `SlidingWindowStrategy`, `SummaryStrategy`) with their use cases, configuration parameters, and trade-offs.
- Document `MessageContextStrategyFactory` — how to build and restore strategies from serialised state (`strategy_type` + `metadata` + `records`).
- Document `MessageRecord` value object — structure, linked-list `prev_id` semantics, and immutability guarantees.

## Capabilities

### New Capabilities

- `message-context-strategy`: Specification for the `MessageContextStrategy` abstract interface, its concrete implementations, the factory, and the `MessageRecord` value object — covering purpose, lifecycle, contracts, and use-case guidance.

### Modified Capabilities

## Impact

- No production code changes; documentation only.
- Affects: `app/domain/entities/context_strategy.py`, `app/domain/entities/session.py` (consumer), `app/adapters/repositories/session_file_adapter.py` (serialisation of strategy state), `tests/domain/entities/test_context_strategy.py`.
