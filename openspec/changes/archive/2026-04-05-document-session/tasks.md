## 1. Verify spec completeness

- [x] 1.1 Read `specs/session/spec.md` and confirm all entities are covered: `update_statistics`, `SessionDto`, `SessionTextChunkEvent`, `SessionCompletionDoneEvent`, `Session.create`, `Session.to_dto`, `Session.from_dto`, `Session.acompletion`, `Session.set_message_context_strategy`
- [x] 1.2 Cross-check each scenario against `tests/domain/entities/test_session.py` to confirm every test case has a matching scenario in the spec
- [x] 1.3 Verify the per-request vs cumulative statistics distinction is explicit in the `SessionCompletionDoneEvent` requirement and the `acompletion` requirement

## 2. Register spec in project-wide index

- [x] 2.1 Copy `specs/session/spec.md` to `openspec/specs/session/spec.md`
- [x] 2.2 Confirm `openspec status` reflects the new spec as a recognised capability

## 3. Add inline docstrings to source

- [x] 3.1 Add a module-level docstring to `app/domain/entities/session.py` referencing the spec location and summarising the aggregate root's role
- [x] 3.2 Add a one-line docstring to `Session.acompletion` describing the event sequence it yields
- [x] 3.3 Add a one-line docstring to `Session.set_message_context_strategy` noting that records are transplanted and the factory rebuild is immediate
- [x] 3.4 Add a one-line docstring to `update_statistics` describing the key format and accumulation behaviour

## 4. Review and close

- [x] 4.1 Review design open question: decide if a `reset_statistics()` method is worth adding; if yes, add a requirement to the spec before archiving
- [x] 4.2 Mark change complete once spec is in `openspec/specs/`, all docstrings are added, and all scenarios are verified against tests
