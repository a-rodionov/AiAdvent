## Context

`MessageContextStrategy` lives in `app/domain/entities/context_strategy.py` and is the sole mechanism through which the `Session` entity controls what conversation history is sent to the LLM on each turn. Three concrete strategies exist today:

- **DummyStrategy** — keeps every record, no pruning.
- **SlidingWindowStrategy** — keeps only the most-recent N records.
- **SummaryStrategy** — calls the LLM to produce a rolling summary once the record count exceeds a window, then discards old records.

Strategy state is serialised by `SessionFileAdapter` as `(type, metadata, records)` and restored via `MessageContextStrategyFactory.build()`. `MessageRecord` is a `NamedTuple` that forms a singly-linked list via `prev_id` UUIDs, preserving insertion order even when records are later trimmed.

The change is **documentation-only**: a single spec file will capture all behavioural contracts so they are machine-readable, reviewable, and testable.

## Goals / Non-Goals

**Goals:**
- Produce a `specs/message-context-strategy/spec.md` that fully specifies the abstract interface contract, each concrete strategy's behaviour, the factory serialisation round-trip, and `MessageRecord` semantics.
- Make every scenario independently testable (they map 1-to-1 with existing test cases in `tests/domain/entities/test_context_strategy.py`).

**Non-Goals:**
- No production code changes.
- No new strategies are designed here.
- No changes to serialisation format or the `SessionDto` schema.

## Decisions

### Decision 1 — one spec file, not four
**Chosen:** All concepts (`MessageContextStrategy`, the three strategies, the factory, `MessageRecord`) in a single `specs/message-context-strategy/spec.md`.

**Alternatives considered:**
- One file per class — splits tightly coupled contracts across files; readers must jump between files to understand the whole lifecycle.
- Separate spec for `MessageRecord` — `MessageRecord` has no independent lifecycle; it only exists within a strategy.

**Rationale:** The strategies, factory, and record type form a cohesive subsystem. A single file keeps cross-references natural and avoids duplication of shared concepts (e.g. linked-list ordering).

### Decision 2 — scenarios derived from existing tests
Each scenario in the spec corresponds to an existing test case in `test_context_strategy.py`. This makes the spec immediately verifiable and avoids speculative requirements that have no test coverage.

### Decision 3 — normalise strategy_type strings as the serialisation key
The factory uses bare string keys (`"dummy"`, `"sliding_window"`, `"summary"`). The spec will codify these as normative string constants so that serialisation-layer code (adapters) and future strategies are unambiguously bound to the same identifiers.

## Risks / Trade-offs

- **Risk: spec drifts from implementation** → Mitigation: scenarios map directly to test functions; CI test failures will flag drift.
- **Risk: SummaryStrategy `_get_history` injects the summary as a `"user"` role message**, which is a surprising protocol choice. The spec documents this behaviour as normative but flags it as a design quirk so future authors don't accidentally "fix" it and break the LLM context format.
- **Trade-off: no new tests added** — the change documents existing behaviour only. Any uncovered edge cases found during spec writing will be noted as open questions rather than silently papered over.

## Open Questions

- Should `SummaryStrategy._get_history()` use `"user"` role for the summary message, or would `"system"` be more semantically correct? Left as-is for now to match current behaviour; worth revisiting if a new LLM provider treats role semantics differently.
