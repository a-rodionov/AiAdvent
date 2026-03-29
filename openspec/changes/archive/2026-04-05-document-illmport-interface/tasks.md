## 1. Document CompletionEvent subclasses

- [x] 1.1 Add Google-style docstring to `TextChunkEvent` describing it as a partial text delta emitted during streaming, with a note on the `text` field
- [x] 1.2 Add Google-style docstring to `CompletionDoneEvent` describing it as the mandatory terminal event carrying final metadata (`provider`, `model`, `tokens_usage`, `stop_reason`, `elapsed_s`)
- [x] 1.3 Add Google-style docstring to `BillingEvent` describing it as an optional cost event carrying `base_input_tokens_cost`, `output_tokens_cost`, `total_cost` in USD

## 2. Document ILlmPort and acompletion

- [x] 2.1 Add class-level docstring to `ILlmPort` explaining its role as a hexagonal-architecture port that isolates the domain from concrete LLM SDKs
- [x] 2.2 Add Google-style docstring to `acompletion` covering: `full_messages` (conversation history in provider-native dict format), `completion_config` (provider/model/sampling settings), `is_stream_prefered` (hint to use streaming API), return type (async generator), and the normative event ordering contract: `TextChunkEvent*`, optional `BillingEvent`, then exactly one terminal `CompletionDoneEvent`

## 3. Create spec file in openspec/specs

- [x] 3.1 Create `openspec/specs/llm-port-contract/spec.md` by merging the change spec from `openspec/changes/document-illmport-interface/specs/llm-port-contract/spec.md` into the canonical specs location

## 4. Verify

- [x] 4.1 Run `mypy app/domain/interfaces/llm_port.py` — confirm no type errors introduced by docstrings
- [x] 4.2 Run `ruff check app/domain/interfaces/llm_port.py` — confirm no lint issues
- [x] 4.3 Run existing test suite (`pytest tests/`) — confirm no regressions
