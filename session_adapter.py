from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

SESSION_INFO = "session_info"
SESSION_MESSAGES = "session_messages"

class SessionDto(BaseModel):
    id: str = Field(min_length=1)
    created_at: datetime
    messages: list = Field(default_factory=list)

class SessionInfoDto(BaseModel):
    id: str = Field(min_length=1)
    created_at: datetime

class SessionMessagesDto(BaseModel):
    messages: list = Field(default_factory=list)

class SessionFileAdapter:
    def __init__(self, dir_path: str):
        path = Path(dir_path)
        if not path.exists():
            raise FileNotFoundError(f"Directory for sessions not found: {path}") 
        self.path: str = path

    def get_session_ids(self) -> list[str]:
        return [entry.name for entry in self.path.iterdir() if entry.is_dir()]

    def get_session(self, id: str) -> SessionDto:
        import json
        info_path = self.path / id / SESSION_INFO
        msgs_path = self.path / id / SESSION_MESSAGES
        try:
            with open(info_path, "r") as f:
                info = SessionInfoDto.model_validate(json.load(f))
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File with part of session info not found: {info_path}") from e
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading session info file: {info_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in session info file: {info_path}") from e

        try:
            with open(msgs_path, "r") as f:
                msgs = SessionMessagesDto.model_validate(json.load(f))
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File with part of session info not found: {msgs_path}") from e
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading session info file: {msgs_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in session info file: {msgs_path}") from e

        return SessionDto(id=info.id, created_at=info.created_at, messages=msgs.messages)
    
    def create_session(self, session: SessionDto) -> None:
        import json
        session_dir = self.path / session.id
        try:
            session_dir.mkdir(exist_ok=False)
        except FileExistsError as e:
            raise FileExistsError(f"Session directory already exists: {session_dir}") from e

        info = SessionInfoDto(id=session.id, created_at=session.created_at)
        msgs = SessionMessagesDto(messages=session.messages)

        try:
            with open(session_dir / SESSION_INFO, "w") as f:
                json.dump(info.model_dump(mode="json"), f)
            with open(session_dir / SESSION_MESSAGES, "w") as f:
                json.dump(msgs.model_dump(mode="json"), f)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when writing session files: {session_dir}") from e
        except OSError as e:
            raise OSError(f"Failed to write session files: {session_dir}") from e

    def update_session(self, session: SessionDto) -> None:
        import json
        session_dir = self.path / session.id
        if not session_dir.exists():
            raise FileNotFoundError(f"Session directory not found: {session_dir}")

        info = SessionInfoDto(id=session.id, created_at=session.created_at)
        msgs = SessionMessagesDto(messages=session.messages)

        try:
            with open(session_dir / SESSION_INFO, "w") as f:
                json.dump(info.model_dump(mode="json"), f)
            with open(session_dir / SESSION_MESSAGES, "w") as f:
                json.dump(msgs.model_dump(mode="json"), f)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when writing session files: {session_dir}") from e
        except OSError as e:
            raise OSError(f"Failed to write session files: {session_dir}") from e

    def delete_session(self, id: str) -> None:
        import shutil
        session_dir = self.path / id
        try:
            shutil.rmtree(session_dir)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Session directory not found: {session_dir}") from e
        except PermissionError as e:
            raise PermissionError(f"Permission denied when deleting session directory: {session_dir}") from e
