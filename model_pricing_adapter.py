from pydantic import ValidationError
from model_pricing import ModelPricingDTO

class ModelPricingFileAdapter:
    def __init__(self, file_path: str):
        import json
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Pricing file not found: {file_path}")

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading pricing file: {file_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in pricing file: {file_path}") from e

        if not isinstance(data["models_pricing"], list):
            raise ValueError("Pricing file must contain JSON attribute models_pricing as an array")

        self._pricing: dict[tuple[str, str], ModelPricingDTO] = {}
        for i, item in enumerate(data["models_pricing"]):
            try:
                dto = ModelPricingDTO.model_validate(item)
            except ValidationError as e:
                raise ValueError(f"Invalid pricing entry at index {i}: {e}") from e
            self._pricing[(dto.provider, dto.model)] = dto

    def get_all_pricing_dtos(self) -> list[ModelPricingDTO]:
        return list(self._pricing.values())
