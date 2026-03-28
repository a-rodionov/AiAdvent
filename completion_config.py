from typing import Optional, List, Type
from pydantic import BaseModel, Field, field_validator, model_validator
from json_heplers import create_model_from_schema


class CompletionConfig(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    max_tokens: int = Field(ge=1)
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, ge=0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stop_sequences: Optional[List[str]] = None
    output_config: Optional[Type[BaseModel]] = None


def format_completion_config(completion_config: CompletionConfig) -> str:
    formated_output = ""
    for name, value in completion_config.model_dump().items():
        if value is not None:
            formated_output += (f"  {name + ':':<21} {value}\n")
    return formated_output


def load_additional_resources(path: str, resource_name: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        raise SystemExit(f"File with {resource_name}  not found: '{path}'")
    except PermissionError:
        raise SystemExit(f"Permission denied when reading {resource_name}: '{path}'")


class CompletionConfigFileAdapter:
    def __init__(self, file_path: str):
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Completion config file not found: {file_path}")

        self._path: str = path

    def create_completion_config(self) -> CompletionConfig:
        import os
        import json
        from pathlib import Path
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading completion config file: {self._path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in completion config file: {self._path}") from e

        if "system_prompt" in data:
            prompt_path = str(Path(os.path.dirname(self._path)) / data["system_prompt"])
            data["system_prompt"] = load_additional_resources(prompt_path, "system_prompt")

        if "output_config" in data:
            output_config_path = str(Path(os.path.dirname(self._path)) / data["output_config"])
            output_config = load_additional_resources(output_config_path, "output_config")
            try:
                data["output_config"] = create_model_from_schema(
                    json.loads(output_config),
                    "OutputModel")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON for output_config in {output_config_path} needed for config file: {self._path}") from e

        try:
            return CompletionConfig.model_validate(data)
        except Exception as e:
            raise SystemExit(f"Completion config error in '{self._path}': {e}")
