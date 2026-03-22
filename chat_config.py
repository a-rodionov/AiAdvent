from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

class ChatConfig(BaseModel):
    default_conversation_config_path: str = Field(min_length=1)
    models_pricing_path: str = Field(min_length=1)

class ChatConfigFileAdapter:
    def __init__(self, file_path: str):
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Chat config file not found: {file_path}")

        self.path: str = path

    def create_chat_config(self) -> ChatConfig:
        import os
        import json
        from pathlib import Path
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
                return ChatConfig.model_validate(data)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading chat config file: {self.path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in chat config file: {self.path}") from e
