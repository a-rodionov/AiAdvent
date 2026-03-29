"""Unit tests for server.domain.value_objects.model_billing.

Covers the ModelBilling engine, DTOs, and cost result types.

Spec: ``openspec/specs/model-pricing/spec.md``
"""
import pytest
from pydantic import ValidationError

from server.application.domain.model.model_billing import (
    ModelBilling,
    TokensCost,
)

# ── TokensCost ────────────────────────────────────────────────────────────────

class TestTokensCost:
    def test_defaults_to_zero(self):
        cost = TokensCost()
        assert cost.prompt_tokens == 0.0
        assert cost.completion_tokens == 0.0
        assert cost.total_tokens == 0.0

    def test_accepts_positive_values(self):
        cost = TokensCost(prompt_tokens=0.003, completion_tokens=0.015, total_tokens=0.018)
        assert cost.prompt_tokens == pytest.approx(0.003)

    def test_rejects_negative_prompt_tokens(self):
        with pytest.raises(ValidationError):
            TokensCost(prompt_tokens=-0.001)

    def test_rejects_negative_completion_tokens(self):
        with pytest.raises(ValidationError):
            TokensCost(completion_tokens=-0.001)

    def test_rejects_negative_total(self):
        with pytest.raises(ValidationError):
            TokensCost(total_tokens=-0.001)


# ── ModelBilling ──────────────────────────────────────────────────────────────

class TestModelBilling:
    def test_construction_with_raw_parameters(self):
        billing = ModelBilling(
            tokens_per_price=1_000_000,
            base_input_tokens=3.0,
            output_tokens=15.0,
        )
        assert isinstance(billing, ModelBilling)

    def test_tokens_per_price_zero_raises(self):
        with pytest.raises(ValueError):
            ModelBilling(tokens_per_price=0, base_input_tokens=3.0, output_tokens=15.0)

    def test_negative_base_input_tokens_raises(self):
        with pytest.raises(ValueError):
            ModelBilling(tokens_per_price=1_000_000, base_input_tokens=-1.0, output_tokens=15.0)

    def test_negative_output_tokens_raises(self):
        with pytest.raises(ValueError):
            ModelBilling(tokens_per_price=1_000_000, base_input_tokens=3.0, output_tokens=-1.0)

    def test_estimate_correct_base_input_cost(self):
        billing = ModelBilling(
            tokens_per_price=1_000_000, base_input_tokens=3.0, output_tokens=15.0
        )
        result = billing.estimate(base_input_tokens=1_000_000, output_tokens=0)
        assert result.prompt_tokens == pytest.approx(3.0)

    def test_estimate_correct_output_cost(self):
        billing = ModelBilling(
            tokens_per_price=1_000_000, base_input_tokens=3.0, output_tokens=15.0
        )
        result = billing.estimate(base_input_tokens=0, output_tokens=1_000_000)
        assert result.completion_tokens == pytest.approx(15.0)

    def test_estimate_correct_total_cost(self):
        billing = ModelBilling(
            tokens_per_price=1_000_000, base_input_tokens=3.0, output_tokens=15.0
        )
        result = billing.estimate(base_input_tokens=1_000_000, output_tokens=1_000_000)
        assert result.total_tokens == pytest.approx(18.0)

    def test_estimate_returns_tokens_cost(self):
        billing = ModelBilling(
            tokens_per_price=1_000_000, base_input_tokens=3.0, output_tokens=15.0
        )
        result = billing.estimate(base_input_tokens=0, output_tokens=0)
        assert isinstance(result, TokensCost)

    def test_estimate_fractional_tokens(self):
        billing = ModelBilling(
            tokens_per_price=1_000, base_input_tokens=1.0, output_tokens=2.0
        )
        result = billing.estimate(base_input_tokens=500, output_tokens=250)
        assert result.prompt_tokens == pytest.approx(0.5)
        assert result.completion_tokens == pytest.approx(0.5)
        assert result.total_tokens == pytest.approx(1.0)

    def test_no_provider_model_parameters_in_estimate(self):
        """ModelBilling.estimate does NOT accept provider or model parameters."""
        billing = ModelBilling(
            tokens_per_price=1_000_000, base_input_tokens=3.0, output_tokens=15.0
        )
        import inspect
        sig = inspect.signature(billing.estimate)
        assert "provider" not in sig.parameters
        assert "model" not in sig.parameters
