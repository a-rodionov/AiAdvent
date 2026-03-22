from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

class ModelPricingDTO(BaseModel):
    model: str = Field(min_length=1)
    tokens_per_price: int = Field(ge=1)
    base_input_tokens: float = Field(ge=0)
    output_tokens: float = Field(ge=0)


class ModelPricingReportDTO(BaseModel):
    model: str = Field(min_length=1)
    base_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    base_input_tokens_cost: float = Field(ge=0)
    output_tokens_cost: float = Field(ge=0)
    total_cost: float = Field(ge=0)


def format_pricing_report(report: ModelPricingReportDTO) -> str:
    return (
        f"Model: {report.model}\n"
        f"Input tokens:  {report.base_input_tokens:>10,}  ${report.base_input_tokens_cost:.6f}\n"
        f"Output tokens: {report.output_tokens:>10,}  ${report.output_tokens_cost:.6f}\n"
        f"Total cost:                ${report.total_cost:.6f}"
    )


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

        self._pricing: dict[str, ModelPricingDTO] = {}
        for i, item in enumerate(data["models_pricing"]):
            try:
                dto = ModelPricingDTO.model_validate(item)
            except ValidationError as e:
                raise ValueError(f"Invalid pricing entry at index {i}: {e}") from e
            self._pricing[dto.model] = dto

    def create_model_pricing(self, model_name: str) -> ModelPricing:
        dto = self._pricing.get(model_name)
        if dto is None:
            raise KeyError(f"No pricing found for model: {model_name}")
        return ModelPricing(dto)


class ModelPricing:
    def __init__(self, model_pricing_dto: ModelPricingDTO):
        if model_pricing_dto is None:
            raise ValueError("model_pricing_dto must not be None")
        self.base_input_tokens: int = 0
        self.output_tokens: int = 0
        self.base_input_tokens_cost: float = 0.0
        self.output_tokens_cost: float = 0.0
        self.total_cost: float = 0.0
        self._model_pricing_dto = model_pricing_dto

    def estimate(self, *, base_input_tokens: int, output_tokens: int) -> None:
        self.base_input_tokens += base_input_tokens
        self.output_tokens += output_tokens
        self.base_input_tokens_cost = self.base_input_tokens * self._model_pricing_dto.base_input_tokens / self._model_pricing_dto.tokens_per_price
        self.output_tokens_cost = self.output_tokens * self._model_pricing_dto.output_tokens / self._model_pricing_dto.tokens_per_price
        self.total_cost = self.base_input_tokens_cost + self.output_tokens_cost

    def get_report(self) -> ModelPricingReportDTO:
        return ModelPricingReportDTO(
            model=self._model_pricing_dto.model,
            base_input_tokens=self.base_input_tokens,
            output_tokens=self.output_tokens,
            base_input_tokens_cost=self.base_input_tokens_cost,
            output_tokens_cost=self.output_tokens_cost,
            total_cost=self.total_cost)
