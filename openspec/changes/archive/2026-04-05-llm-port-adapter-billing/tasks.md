## 1. context_strategy.py — New failing tests (red)

- [x] 1.1 In `test_context_strategy.py`, add test: `SummaryStrategy._apply_strategy` with `BillingEvent` present — verify `_emit_token_usage` is called with `prompt_tokens=0`, `completion_tokens=0`, and billing cost fields
- [x] 1.2 In `test_context_strategy.py`, add test: `SummaryStrategy._apply_strategy` with no `BillingEvent` — verify `_emit_token_usage` is called with token counts from `CompletionDoneEvent` and all cost args `0.0`

## 2. context_strategy.py — Implementation (green)

- [x] 2.1 Update `TokenUsageHandler` type alias to `Callable[[str, str, int, int, float, float, float], None]`
- [x] 2.2 Update `_emit_token_usage` method signature to add `base_input_tokens_cost: float`, `output_tokens_cost: float`, `total_cost: float` parameters; forward all seven args to each handler
- [x] 2.3 Update `SummaryStrategy._apply_strategy` to set `billing_event: BillingEvent | None = None`; assign on `BillingEvent` instance; after the loop call `_emit_token_usage` with cost fields from `billing_event` when present (`prompt_tokens=0`, `completion_tokens=0`) or with token counts from `CompletionDoneEvent` and zeros for costs when absent
- [x] 2.4 Fix broken call sites in `test_context_strategy.py` that use the old `_emit_token_usage` / `TokenUsageHandler` four-arg shape

## 3. session.py — New failing tests (red)

- [x] 3.1 In `test_session.py`, add test: `update_statistics` accumulates `base_input_tokens_cost`, `output_tokens_cost`, `total_cost` directly from caller-supplied args (no `model_pricing`)
- [x] 3.2 In `test_session.py`, add test: `Session.acompletion` with `BillingEvent` present — verify `session.statistics` entry has `tokens_cost.total_tokens` equal to the billing event's `total_cost`
- [x] 3.3 In `test_session.py`, add test: `Session.acompletion` with no `BillingEvent` — verify `tokens_cost.total_tokens` is `0.0`

## 4. session.py — Implementation (green)

- [x] 4.1 Update `update_statistics` signature to `(usage_statistics, provider, model, prompt_tokens, completion_tokens, base_input_tokens_cost, output_tokens_cost, total_cost)`; remove `model_pricing` param and `model_pricing.estimate()` call; assign cost fields directly to `TokensCost`
- [x] 4.2 Update `Session._handle_token_usage` signature to add `base_input_tokens_cost: float`, `output_tokens_cost: float`, `total_cost: float`; forward all params to both `update_statistics` calls (cumulative and per-request)
- [x] 4.3 Update `Session.acompletion` event loop: add `billing_event: BillingEvent | None = None`; assign on `isinstance(event, BillingEvent)`; when `CompletionDoneEvent` arrives call `_handle_token_usage` with token counts from done event and cost fields from `billing_event` (defaults `0.0` when absent)
- [x] 4.4 Remove `model_pricing` param from `Session.__init__`; remove `self._model_pricing` attribute
- [x] 4.5 Remove `model_pricing` param from `Session.create` classmethod; update its `cls(...)` call accordingly
- [x] 4.6 Remove `model_pricing` param from `Session.from_dto` classmethod; update its `cls(...)` call accordingly
- [x] 4.7 Fix broken call sites in `test_session.py` that construct `Session` or call `update_statistics` / `_handle_token_usage` with old signatures

## 5. Use-case and infrastructure call sites

- [x] 5.1 Update `CreateSession.__init__` and `execute()` to remove `model_pricing` — drop the field and stop passing it to `Session.create`
- [x] 5.2 Update `GetSession.__init__` and `execute()` to remove `model_pricing` — drop the field and stop passing it to `Session.from_dto`
- [x] 5.3 Update `app_factory.py` to stop constructing / injecting `ModelPricing` into `CreateSession` and `GetSession` (remove `ModelPricing.from_dtos` call if it is now unused in the factory)
- [x] 5.4 Fix `test_create_session.py` — remove `model_pricing` fixture / mock and update `CreateSession` construction
- [x] 5.5 Fix `test_get_session.py` — remove `model_pricing` fixture / mock and update `GetSession` construction
- [x] 5.6 Audit `test_send_message.py` for any `Session.create` or `Session.from_dto` calls that pass `model_pricing`; update if present
