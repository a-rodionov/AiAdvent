import json
from dataclasses import dataclass, fields
from typing import Optional, List

@dataclass
class OutputConfig:
    json_schema: dict

# --- Data class to represent the model config ---
@dataclass
class ModelConfig:
    model: str
    max_tokens: int
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    output_config: Optional[OutputConfig] = None

    def print_config(self) -> None:
        print("=== Full Configuration ===")
        for f in fields(self):
            value = getattr(self, f.name)
            if value is not None:
                print(f"  {f.name:<20} {value}")

def _validate_max_tokens(value: int) -> int:
    if value < 1:
        raise ValueError(f"max_tokens must be >= 1, got {value}")
    return value

def _validate_temperature(value: float) -> float:
    if value < 0 or value > 1:
        raise ValueError(f"temperature must be between 0 and 1, got {value}")
    return value

def _validate_top_k(value: int) -> int:
    if value < 0:
        raise ValueError(f"top_k must be >= 0, got {value}")
    return value

def _validate_top_p(value: float) -> float:
    if value < 0 or value > 1:
        raise ValueError(f"top_p must be between 0 and 1, got {value}")
    return value

def parse_model_config(json_input: str | dict) -> ModelConfig:
    """Parse a JSON string or dict into a ModelConfig object."""

    # Accept both raw JSON string and already-parsed dict
    if isinstance(json_input, str):
        try:
            data = json.loads(json_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    else:
        data = json_input

    required = ["model", "max_tokens"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    return ModelConfig(
        model=str(data["model"]),
        max_tokens=_validate_max_tokens(int(data["max_tokens"])),
        system_prompt=str(data["system_prompt"]) if "system_prompt" in data else None,
        temperature=_validate_temperature(float(data["temperature"])) if "temperature" in data else None,
        top_k=_validate_top_k(int(data["top_k"])) if "top_k" in data else None,
        top_p=_validate_top_p(float(data["top_p"])) if "top_p" in data else None,
        stop_sequences=[str(s) for s in data["stop_sequences"]] if "stop_sequences" in data else None,
        output_config=OutputConfig(data["output_config"]["json_schema"]) if "output_config" in data else None,
    )

def load_config(path: str) -> ModelConfig:
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"[ERROR] File not found: '{path}'")
    except PermissionError:
        raise SystemExit(f"[ERROR] Permission denied when reading: '{path}'")
    except json.JSONDecodeError as e:
        raise SystemExit(f"[ERROR] Invalid JSON in '{path}': {e}")

    try:
        return parse_model_config(data)
    except ValueError as e:
        raise SystemExit(f"[ERROR] Configuration error in '{path}': {e}")
