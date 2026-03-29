"""ModelBillingFactoryAdapter — reads pricing file and creates ModelBilling instances.

Spec: ``openspec/specs/model-billing-factory/spec.md``
"""
import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from server.application.domain.model.model_billing import ModelBilling

# ── Pricing data transfer object ──────────────────────────────────────────────

class ModelCostDTO(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tokens_per_price: int = Field(ge=1)
    base_input_tokens: float = Field(ge=0)
    output_tokens: float = Field(ge=0)


class ModelBillingFactoryAdapter:
    """Reads a pricing JSON file, caches DTOs, and creates ModelBilling on demand."""

    def __init__(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Model billing file not found: {file_path}")

        try:
            with open(path) as f:
                data = json.load(f)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading pricing file: {file_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in pricing file: {file_path}") from e

        if not isinstance(data["models_cost"], list):
            raise ValueError("Model billing file must contain JSON attribute models_cost as an array")

        self._pricing: dict[tuple[str, str], ModelCostDTO] = {}
        for i, item in enumerate(data["models_cost"]):
            try:
                dto = ModelCostDTO.model_validate(item)
            except ValidationError as e:
                raise ValueError(f"Invalid pricing entry at index {i}: {e}") from e
            self._pricing[(dto.provider, dto.model)] = dto

    def create(self, provider: str, model: str) -> ModelBilling | None:
        """Return a ModelBilling for the given pair, or None if not found."""
        dto = self._pricing.get((provider, model))
        if dto is None:
            return None
        return ModelBilling(
            tokens_per_price=dto.tokens_per_price,
            base_input_tokens=dto.base_input_tokens,
            output_tokens=dto.output_tokens,
        )
