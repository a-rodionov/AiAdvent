"""Billing value objects for LLM cost estimation and statistics tracking.

Contains the billing engine (:class:`ModelBilling`), its supporting DTOs and
result types, and the session-side cost accumulation models.

Spec: ``openspec/specs/model-pricing/spec.md``
"""
from pydantic import BaseModel, Field

# ── Session-side cost tracking ────────────────────────────────────────────────

class TokensCost(BaseModel):
    prompt_tokens: float = Field(default=0.0, ge=0)
    completion_tokens: float = Field(default=0.0, ge=0)
    total_tokens: float = Field(default=0.0, ge=0)


# ── Billing engine ────────────────────────────────────────────────────────────

class ModelBilling:
    def __init__(self, tokens_per_price: int, base_input_tokens: float, output_tokens: float):
        """Build the billing engine for a specific provider/model pair.

        Args:
            tokens_per_price: Number of tokens per pricing unit (e.g. 1_000_000).
            base_input_tokens: Cost per `tokens_per_price` input tokens (USD).
            output_tokens: Cost per `tokens_per_price` output tokens (USD).
        """
        if tokens_per_price < 1:
            raise ValueError(f"tokens_per_price must be >= 1, got {tokens_per_price}")
        if base_input_tokens < 0:
            raise ValueError(f"base_input_tokens must be >= 0, got {base_input_tokens}")
        if output_tokens < 0:
            raise ValueError(f"output_tokens must be >= 0, got {output_tokens}")
        self._tokens_per_price = tokens_per_price
        self._base_input_tokens = base_input_tokens
        self._output_tokens = output_tokens

    def estimate(self, *, base_input_tokens: int, output_tokens: int) -> TokensCost:
        """Return costs via ``cost = token_count * rate / tokens_per_price``."""
        prompt_tokens = base_input_tokens * self._base_input_tokens / self._tokens_per_price
        completion_tokens = output_tokens * self._output_tokens / self._tokens_per_price
        total_tokens = prompt_tokens + completion_tokens
        return TokensCost(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens)
