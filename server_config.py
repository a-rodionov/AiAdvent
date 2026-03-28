from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

class ServerConfig(BaseModel):
    log_level: Literal["debug", "info", "warning", "error", "critical"] = Field(default="info")
    host: str = Field(min_length=1)
    port:int = Field(ge=1)
    default_completion_config_path: str = Field(min_length=1)
    models_pricing_path: str = Field(min_length=1)
    session_storage_dir: str = Field(min_length=1)

def get_server_config(file_path: str) -> ServerConfig:
    import os
    import json
    from pathlib import Path
    
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Server config file not found: {file_path}")

    try:
        with open(path, "r") as f:
            data = json.load(f)
            return ServerConfig.model_validate(data)
    except PermissionError as e:
        raise PermissionError(f"Permission denied when reading server config file: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in server config file: {path}") from e
