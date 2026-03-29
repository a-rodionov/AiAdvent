## ADDED Requirements

### Requirement: LlmStatsDecorator construction
`LlmStatsDecorator` is a domain-layer class that wraps an `ILlmPort` instance. Its constructor SHALL accept three parameters: `llm` (an object satisfying the `ILlmPort` Protocol), `usage_stats` (a `SessionUsageStats` instance for accumulating token usage), and `billing` (an optional `ModelBilling` instance, defaulting to `None`). All three SHALL be stored as private members.

#### Scenario: construction with all parameters
- **WHEN** `LlmStatsDecorator(llm=llm, usage_stats=stats, billing=billing)` is called
- **THEN** the instance is created with all three members accessible internally

#### Scenario: construction without billing
- **WHEN** `LlmStatsDecorator(llm=llm, usage_stats=stats)` is called
- **THEN** the instance is created with `billing` set to `None`

---

### Requirement: LlmStatsDecorator satisfies ILlmPort Protocol
`LlmStatsDecorator` SHALL expose an `acompletion` method with the same signature as `ILlmPort.acompletion`: `acompletion(full_messages: list, completion_config: CompletionConfig, is_stream_prefered: bool) -> AsyncGenerator[CompletionEvent, None]`. This makes `LlmStatsDecorator` structurally compatible with the `ILlmPort` Protocol and usable anywhere an `ILlmPort` is expected.

#### Scenario: LlmStatsDecorator is accepted where ILlmPort is expected
- **WHEN** a function parameter is typed as `ILlmPort` and a `LlmStatsDecorator` instance is passed
- **THEN** mypy SHALL accept it without type errors (structural subtyping via Protocol)

---

### Requirement: LlmStatsDecorator passes TextChunkEvent through unchanged
When the wrapped `ILlmPort.acompletion` yields a `TextChunkEvent`, `LlmStatsDecorator.acompletion` SHALL yield the same `TextChunkEvent` instance to the caller without modification or delay.

#### Scenario: text chunks are forwarded
- **WHEN** the wrapped LLM yields `TextChunkEvent(text="Hello")`
- **THEN** `LlmStatsDecorator.acompletion` yields the same `TextChunkEvent(text="Hello")`

#### Scenario: multiple text chunks preserve order
- **WHEN** the wrapped LLM yields `TextChunkEvent(text="A")` then `TextChunkEvent(text="B")`
- **THEN** `LlmStatsDecorator.acompletion` yields them in the same order

---

### Requirement: LlmStatsDecorator intercepts CompletionDoneEvent for stats accumulation
When the wrapped `ILlmPort.acompletion` yields a `CompletionDoneEvent`, `LlmStatsDecorator` SHALL extract `provider`, `model`, and `tokens_usage` from the event. If `billing` is not `None`, it SHALL call `billing.estimate(provider=provider, model=model, base_input_tokens=tokens_usage.prompt_tokens, output_tokens=tokens_usage.completion_tokens)` to obtain a `PricingResult`, then construct a `TokensCost` from the result. It SHALL then call `usage_stats.add_stats(provider, model, usage=tokens_usage, cost=cost)` where `cost` is the constructed `TokensCost` or `None` if no `billing` was provided. After stats accumulation, it SHALL yield the original `CompletionDoneEvent` to the caller.

#### Scenario: stats accumulated without billing
- **WHEN** `billing` is `None` and the wrapped LLM yields `CompletionDoneEvent(provider="anthropic", model="claude-3", tokens_usage=TokensUsage(prompt_tokens=100, completion_tokens=50), ...)`
- **THEN** `usage_stats.add_stats("anthropic", "claude-3", usage=TokensUsage(prompt_tokens=100, completion_tokens=50), cost=None)` is called and the `CompletionDoneEvent` is yielded

#### Scenario: stats accumulated with billing
- **WHEN** `billing` is provided and `billing.estimate(...)` returns `PricingResult(base_input_tokens_cost=0.003, output_tokens_cost=0.015, total_cost=0.018)`
- **THEN** `usage_stats.add_stats` is called with `cost=TokensCost(prompt_tokens=0.003, completion_tokens=0.015, total_tokens=0.018)` and the `CompletionDoneEvent` is yielded

#### Scenario: CompletionDoneEvent is yielded after stats accumulation
- **WHEN** the wrapped LLM yields a `CompletionDoneEvent`
- **THEN** the decorator yields the same `CompletionDoneEvent` instance after calling `add_stats`

---

### Requirement: LlmStatsDecorator handles ModelBilling KeyError gracefully
If `billing.estimate()` raises `KeyError` (unknown provider/model pair), `LlmStatsDecorator` SHALL call `usage_stats.add_stats` with `cost=None` and yield the `CompletionDoneEvent` normally. The `KeyError` SHALL NOT propagate to the caller.

#### Scenario: unknown model falls back to no cost
- **WHEN** `billing.estimate()` raises `KeyError` for an unknown model
- **THEN** `usage_stats.add_stats` is called with `cost=None` and the `CompletionDoneEvent` is yielded without error

---

### Requirement: LlmStatsDecorator delegates all arguments to wrapped ILlmPort
`LlmStatsDecorator.acompletion` SHALL forward `full_messages`, `completion_config`, and `is_stream_prefered` to the wrapped `ILlmPort.acompletion` without modification.

#### Scenario: arguments are forwarded verbatim
- **WHEN** `LlmStatsDecorator.acompletion(messages, config, True)` is called
- **THEN** the wrapped `ILlmPort.acompletion` receives the same `messages`, `config`, and `True` arguments
