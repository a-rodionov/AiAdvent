"""Unit tests for server.adapter.outbound.persistence.model_billing_factory_adapter.

Covers the ModelCostDTO.

Spec: ``openspec/specs/model-billing-factory/spec.md``
"""
import pytest
from pydantic import ValidationError

from server.adapter.outbound.persistence.model_billing_factory_adapter import ModelCostDTO

# ── ModelCostDTO ───────────────────────────────────────────────────────────

class TestModelPricingDTO:
    def test_valid_dto(self):
        dto = ModelCostDTO(
            provider="openai",
            model="gpt-4",
            tokens_per_price=1_000_000,
            base_input_tokens=3.0,
            output_tokens=15.0,
        )
        assert dto.provider == "openai"
        assert dto.tokens_per_price == 1_000_000

    def test_empty_provider_raises(self):
        with pytest.raises(ValidationError):
            ModelCostDTO(
                provider="",
                model="m",
                tokens_per_price=1,
                base_input_tokens=1.0,
                output_tokens=1.0,
            )

    def test_empty_model_raises(self):
        with pytest.raises(ValidationError):
            ModelCostDTO(
                provider="p",
                model="",
                tokens_per_price=1,
                base_input_tokens=1.0,
                output_tokens=1.0,
            )

    def test_tokens_per_price_zero_raises(self):
        with pytest.raises(ValidationError):
            ModelCostDTO(
                provider="p",
                model="m",
                tokens_per_price=0,
                base_input_tokens=1.0,
                output_tokens=1.0,
            )

    def test_negative_base_input_price_raises(self):
        with pytest.raises(ValidationError):
            ModelCostDTO(
                provider="p",
                model="m",
                tokens_per_price=1,
                base_input_tokens=-0.1,
                output_tokens=1.0,
            )

    def test_negative_output_price_raises(self):
        with pytest.raises(ValidationError):
            ModelCostDTO(
                provider="p",
                model="m",
                tokens_per_price=1,
                base_input_tokens=1.0,
                output_tokens=-0.1,
            )

    def test_zero_prices_valid(self):
        dto = ModelCostDTO(
            provider="p",
            model="m",
            tokens_per_price=1,
            base_input_tokens=0.0,
            output_tokens=0.0,
        )
        assert dto.base_input_tokens == 0.0
        assert dto.output_tokens == 0.0

