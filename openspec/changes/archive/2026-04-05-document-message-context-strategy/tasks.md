## 1. Verify spec file is complete and consistent

- [x] 1.1 Read `specs/message-context-strategy/spec.md` and confirm all five entities are covered: `MessageRecord`, `MessageContextStrategy`, `DummyStrategy`, `SlidingWindowStrategy`, `SummaryStrategy`, and `MessageContextStrategyFactory`
- [x] 1.2 Cross-check each scenario against `tests/domain/entities/test_context_strategy.py` to confirm every test case has a matching scenario in the spec
- [x] 1.3 Verify that `strategy_type` string constants (`"dummy"`, `"sliding_window"`, `"summary"`) appear verbatim in the spec requirements

## 2. Register the spec in the openspec index

- [x] 2.1 Move or copy `specs/message-context-strategy/spec.md` to `openspec/specs/message-context-strategy/spec.md` so it is tracked by the project-wide spec registry
- [x] 2.2 Confirm `openspec status` reflects the new spec as a recognised capability

## 3. Add inline docstrings to source (optional enrichment)

- [x] 3.1 Add a module-level docstring to `app/domain/entities/context_strategy.py` referencing the spec location
- [x] 3.2 Add a one-line docstring to each abstract method (`_apply_strategy`, `_get_history`, `get_metadata`, `strategy_type`) summarising its contract as stated in the spec

## 4. Review and close

- [x] 4.1 Review `design.md` open question: decide whether `SummaryStrategy._get_history()` should use `"user"` role or `"system"` role for the summary message, and update spec if behaviour changes
- [x] 4.2 Mark change as complete once all spec scenarios are verified against tests and the spec file is in `openspec/specs/`
