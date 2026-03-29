import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.context_strategy import MessageContextStrategyDefaults

# ── Server configuration model ────────────────────────────────────────────────

class ServerConfig(BaseModel):
    log_level: Literal["debug", "info", "warning", "error", "critical"] = Field(default="info")
    host: str = Field(min_length=1)
    port: int = Field(ge=1)
    default_completion_config: CompletionConfig
    models_billing_path: str = Field(min_length=1)
    session_storage_path: str = Field(min_length=1)
    message_context_strategies_path: str = Field(min_length=1)
    default_message_context_strategy: str = Field(min_length=1)


# ── File I/O helpers for CompletionConfig ─────────────────────────────────────

def _load_resource(path: str, resource_name: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError as e:
        raise SystemExit(f"File with {resource_name} not found: '{path}'") from e
    except PermissionError as e:
        raise SystemExit(f"Permission denied when reading {resource_name}: '{path}'") from e


def resolve_completion_config(raw: dict, base_dir: str) -> dict:
    """Load file-referenced resources into a raw CompletionConfig dict.

    Reads system_prompt_path and output_config_path relative to base_dir,
    inlining their contents so that the dict can be passed directly to
    CompletionConfig.model_validate without any Pydantic context.
    """
    raw = dict(raw)  # shallow copy — do not mutate the caller's dict
    if raw.get("system_prompt_path"):
        path = os.path.join(base_dir, raw["system_prompt_path"])
        raw["system_prompt"] = _load_resource(path, "system_prompt")
    if raw.get("output_config_path"):
        path = os.path.join(base_dir, raw["output_config_path"])
        schema_text = _load_resource(path, "output_config")
        from common.json_helpers import create_model_from_schema
        try:
            raw["output_config"] = create_model_from_schema(json.loads(schema_text), "OutputModel")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON for output_config in {path}") from e
    return raw


def serialize_completion_config(config: CompletionConfig, save_dir: str) -> dict:
    """Serialize a CompletionConfig to a plain dict, writing large resources to disk.

    Writes system_prompt to a .txt file and output_config schema to a .json
    file under save_dir, storing only the filenames in the returned dict.
    """
    os.makedirs(save_dir, exist_ok=True)
    data = config.model_dump(mode="json")

    if data.get("system_prompt"):
        filename = data.get("system_prompt_path")
        if not filename:
            prompt_hash = hashlib.md5(data["system_prompt"].encode()).hexdigest()[:8]
            filename = f"system_prompt_{prompt_hash}.txt"
        with open(os.path.join(save_dir, filename), "w", encoding="utf-8") as f:
            f.write(data["system_prompt"])
        data["system_prompt_path"] = filename
        del data["system_prompt"]

    if config.output_config is not None:
        schema_str = json.dumps(config.output_config.model_json_schema(), indent=2)
        filename = data.get("output_config_path")
        if not filename:
            schema_hash = hashlib.md5(schema_str.encode()).hexdigest()[:8]
            filename = f"output_config_{schema_hash}.json"
        with open(os.path.join(save_dir, filename), "w", encoding="utf-8") as f:
            f.write(schema_str)
        data["output_config_path"] = filename
        data.pop("output_config", None)

    return data


# ── Message context strategies loader ────────────────────────────────────────

def load_message_context_strategies(path: str, base_dir: str) -> dict[str, MessageContextStrategyDefaults]:
    """Load and parse message context strategies from a JSON file.

    Resolves file references (prompt_path, system_prompt_path, output_config_path)
    relative to base_dir. Returns a dict keyed by strategy type.
    """
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise SystemExit(f"Message context strategies file not found: '{path}'") from e
    except PermissionError as e:
        raise SystemExit(f"Permission denied when reading message context strategies file: '{path}'") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in message context strategies file: {path}") from e

    result: dict[str, MessageContextStrategyDefaults] = {}
    for entry in data.get("message_context_strategies", []):
        entry = dict(entry)  # shallow copy
        strategy_type = entry.pop("type")
        raw_completion_config = entry.pop("completion_config")
        prompt_path = entry.pop("prompt_path", None)

        metadata: dict = {}
        if prompt_path is not None:
            full_prompt_path = os.path.join(base_dir, prompt_path)
            metadata["summarization_prompt"] = _load_resource(full_prompt_path, "summarization_prompt")
        if "window_size" in entry:
            metadata["window_size"] = entry.pop("window_size")
        # Any remaining non-type, non-completion_config, non-prompt_path keys
        for key, value in entry.items():
            metadata[key] = value

        resolved_config = resolve_completion_config(raw_completion_config, base_dir)
        completion_config = CompletionConfig.model_validate(resolved_config)

        result[strategy_type] = MessageContextStrategyDefaults(
            type=strategy_type,
            completion_config=completion_config,
            metadata=metadata,
        )

    return result


# ── Server config loader ──────────────────────────────────────────────────────

def get_server_config(file_path: str) -> ServerConfig:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Server config file not found: {file_path}")

    try:
        with open(path) as f:
            data = json.load(f)
    except PermissionError as e:
        raise PermissionError(f"Permission denied when reading server config file: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in server config file: {path}") from e

    base_dir = str(path.parent)

    # Resolve file references in CompletionConfig fields before Pydantic validation.
    if "default_completion_config" in data:
        data["default_completion_config"] = resolve_completion_config(
            data["default_completion_config"], base_dir
        )

    return ServerConfig.model_validate(data)
