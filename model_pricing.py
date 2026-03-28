from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError
from typing import NamedTuple


class ModelPricingDTO(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tokens_per_price: int = Field(ge=1)
    base_input_tokens: float = Field(ge=0)
    output_tokens: float = Field(ge=0)


class TokensCost(NamedTuple):
    base_input_tokens_cost: float
    output_tokens_cost: float
    total_cost: float


class ModelPricing:
    def __init__(self, model_pricing_dtos: list[ModelPricingDTO]):
        if not model_pricing_dtos:
            raise ValueError("model_pricing_dtos must not be empty")
        self._pricing: dict[tuple[str, str], tuple[int, float, float]] = {
            (dto.provider, dto.model): (dto.tokens_per_price, dto.base_input_tokens, dto.output_tokens)
            for dto in model_pricing_dtos
        }

    @classmethod
    def from_dtos(cls, dtos: list[ModelPricingDTO]) -> "ModelPricing":
        return cls(dtos)

    def estimate(self, *, provider: str, model: str, base_input_tokens: int, output_tokens: int) -> TokensCost:
        key = (provider, model)
        if key not in self._pricing:
            raise KeyError(f"No pricing found for provider='{provider}', model='{model}'")
        tokens_per_price, base_input_price, output_price = self._pricing[key]
        base_input_tokens_cost = base_input_tokens * base_input_price / tokens_per_price
        output_tokens_cost = output_tokens * output_price / tokens_per_price
        total_cost = base_input_tokens_cost + output_tokens_cost
        return TokensCost(base_input_tokens_cost, output_tokens_cost, total_cost)
