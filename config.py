import json
from dataclasses import dataclass
from typing import Optional

# --- Data class to represent the model config ---
@dataclass
class ModelConfig:
    model: str
    max_tokens: int
    temperature: float
    top_k: int
    top_p: float

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

    # Validate required fields
    required_fields = [
        "model", "max_tokens", "temperature", "top_k", "top_p"
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    return ModelConfig(
        model=str(data["model"]),
        max_tokens=int(data["max_tokens"]),
        temperature=float(data["temperature"]),
        top_k=int(data["top_k"]),
        top_p=float(data["top_p"]),
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
