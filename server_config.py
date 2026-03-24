from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

class ServerConfig(BaseModel):
    log_level: Literal["debug", "info", "warning", "error", "critical"] = Field(default="info")    
    host: str = Field(min_length=1)
    port:int = Field(ge=1)
    default_conversation_config_path: str = Field(min_length=1)
    models_pricing_path: str = Field(min_length=1)

def format_server_config(server_config: ServerConfig) -> str:
    formatted_output = ""
    for name, value in server_config.model_dump().items():
        if value is not None:
            formatted_output += (f"  {name + ':':<35} {value}\n")
    return formatted_output


class ServerConfigFileAdapter:
    def __init__(self, file_path: str):
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Server config file not found: {file_path}")

        self.path: str = path

    def create_server_config(self) -> ServerConfig:
        import os
        import json
        from pathlib import Path
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
                return ServerConfig.model_validate(data)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading server config file: {self.path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in server config file: {self.path}") from e
