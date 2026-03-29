## ADDED Requirements

### Requirement: Session propagates BillingEvent cost to usage statistics
`Session.acompletion` SHALL inspect every event yielded by `ILlmPort.acompletion`. When a `BillingEvent` is received the session SHALL capture `provider`, `model`, `base_input_tokens_cost`, `output_tokens_cost`, and `total_cost` from it. When `CompletionDoneEvent` arrives the session SHALL call `_handle_token_usage` with the captured billing figures (using `prompt_tokens=0` and `completion_tokens=0` when a `BillingEvent` was received, so that token counts originate from `CompletionDoneEvent` while costs originate exclusively from `BillingEvent`). When no `BillingEvent` is present all cost arguments to `_handle_token_usage` SHALL default to `0.0`.

#### Scenario: BillingEvent cost fields are forwarded to _handle_token_usage
- **WHEN** `acompletion` receives a `BillingEvent` with `base_input_tokens_cost=0.002`, `output_tokens_cost=0.006`, `total_cost=0.008` before the terminal `CompletionDoneEvent`
- **THEN** `_handle_token_usage` is called with `base_input_tokens_cost=0.002`, `output_tokens_cost=0.006`, `total_cost=0.008`

#### Scenario: session statistics reflect BillingEvent costs instead of computed estimates
- **WHEN** `acompletion` completes and a `BillingEvent` with `total_cost=0.05` was in the stream
- **THEN** the per-request `statistics` entry for that provider/model has `tokens_cost.total_tokens` equal to `0.05`

#### Scenario: absent BillingEvent yields zero cost in statistics
- **WHEN** `acompletion` completes and no `BillingEvent` was in the stream
- **THEN** the per-request `statistics` entry for that provider/model has `tokens_cost.total_tokens` equal to `0.0`

#### Scenario: token counts still come from CompletionDoneEvent
- **WHEN** `acompletion` completes with a `BillingEvent` present and `CompletionDoneEvent` reports `prompt_tokens=10, completion_tokens=5`
- **THEN** the per-request `statistics` entry shows `tokens_usage.prompt_tokens=10` and `tokens_usage.completion_tokens=5`

---

### Requirement: SummaryStrategy propagates BillingEvent cost through _emit_token_usage
`SummaryStrategy._apply_strategy` SHALL consume the event stream from its internal LLM summarisation call. When a `BillingEvent` is present in that stream, the strategy SHALL call `_emit_token_usage` with `prompt_tokens=0`, `completion_tokens=0`, and the cost fields (`base_input_tokens_cost`, `output_tokens_cost`, `total_cost`) taken from the `BillingEvent`. When no `BillingEvent` is present, cost arguments SHALL default to `0.0` and token counts SHALL come from `CompletionDoneEvent`.

#### Scenario: BillingEvent cost fields are forwarded to _emit_token_usage during summarisation
- **WHEN** the LLM stream during summarisation includes a `BillingEvent` with `base_input_tokens_cost=0.001`, `output_tokens_cost=0.003`, `total_cost=0.004`
- **THEN** `_emit_token_usage` is called with `base_input_tokens_cost=0.001`, `output_tokens_cost=0.003`, `total_cost=0.004`

#### Scenario: prompt_tokens and completion_tokens are zero when BillingEvent is present
- **WHEN** a `BillingEvent` is present in the summarisation stream
- **THEN** `_emit_token_usage` is called with `prompt_tokens=0` and `completion_tokens=0`

#### Scenario: absent BillingEvent yields zero cost and token counts from CompletionDoneEvent
- **WHEN** no `BillingEvent` appears in the summarisation stream and `CompletionDoneEvent` reports `prompt_tokens=8, completion_tokens=4`
- **THEN** `_emit_token_usage` is called with `prompt_tokens=8`, `completion_tokens=4`, and all cost arguments equal to `0.0`
