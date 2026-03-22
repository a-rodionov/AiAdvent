from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator


class OutputConfig(BaseModel):
    json_schema: dict = Field(min_length=1)


class ConversationConfig(BaseModel):
    model: str = Field(min_length=1)
    max_tokens: int = Field(ge=1)
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, ge=0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stop_sequences: Optional[List[str]] = None
    output_config: Optional[OutputConfig] = None

def format_conversation_config(conversation_config: ConversationConfig) -> str:
    formated_output = ""
    for name, value in conversation_config.model_dump().items():
        if value is not None:
            formated_output += (f"  {name + ':':<21} {value}\n")
    return formated_output


def load_system_prompt(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        raise SystemExit(f"System prompt file not found: '{path}'")
    except PermissionError:
        raise SystemExit(f"Permission denied when reading system prompt: '{path}'")


class ConversationConfigFileAdapter:
    def __init__(self, file_path: str):
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Conversation config file not found: {file_path}")

        self.path: str = path

    def create_conversation_config(self) -> ConversationConfig:
        import os
        import json
        from pathlib import Path
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading conversation config file: {self.path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in conversation config file: {self.path}") from e

        if "system_prompt" in data:
            prompt_path = str(Path(os.path.dirname(self.path)) / data["system_prompt"])
            data["system_prompt"] = load_system_prompt(prompt_path)
        
        try:
            return ConversationConfig.model_validate(data)
        except Exception as e:
            raise SystemExit(f"Configuration error in '{self.path}': {e}")
