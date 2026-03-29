### Running Tests

```bash
./run_tests.sh                  # all tests
./run_tests.sh -v               # verbose
./run_tests.sh -k <pattern>     # filter by name
./run_tests.sh --cov            # with coverage
./run_tests.sh --cov-check      # coverage + per-directory thresholds
```

### Test Structure

- `tests/domain/entities/` — unit tests for domain entities (Session, MessageContextStrategy)
- `tests/domain/value_objects/` — unit tests for value objects (Completion, Pricing, UsageStats)
- `tests/use_cases/` — unit tests for use case services (with mock ports in `conftest.py`)

### Coverage Thresholds

- `server/application/domain/model/` — 95%
- `server/application/domain/service/` — 95%
- `server/adapter/` — 0% (adapter tests optional)
- `server/` total — 0%

### Test Configuration

- `pytest.ini`: testpaths=`tests`, asyncio_mode=`auto`
- Async tests run natively without markers

### Testing Methodology

- Every change to domain layers**must** be covered with unit tests.
- Tests for adapters and common layers may be omitted.
- Use scenarios from specs (`openspec/specs/`) for additional test cases.
