import json
import shutil
import uuid as _uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.usage_stats import ModelStats
from server.application.port.outbound.session_repository import ISessionRepository

if TYPE_CHECKING:
    from server.application.domain.model.session import Session, SessionState

SESSION_INFO = "session_info"
SESSION_MESSAGES = "session_messages"


class MessageRecordDto(BaseModel):
    id: str
    prev_id: str | None = None
    message: dict[str, str]


class MessageContextStrategyInfoDto(BaseModel):
    type: str
    metadata: dict[str, Any]
    completion_config: CompletionConfig


class SessionInfoDto(BaseModel):
    id: str = Field(min_length=1)
    created_at: datetime
    completion_config: CompletionConfig
    statistics: dict[str, dict[str, ModelStats]] | None = None
    message_context_strategy: MessageContextStrategyInfoDto | None = None


class SessionMessagesDto(BaseModel):
    records: list[MessageRecordDto] = Field(default_factory=list)


class SessionFileAdapter(ISessionRepository):
    def __init__(self, dir_path: str):
        path = Path(dir_path)
        if not path.exists():
            raise FileNotFoundError(f"Directory for sessions not found: {path}")
        self._path: Path = path

    def get_session_ids(self) -> list[str]:
        return [entry.name for entry in self._path.iterdir() if entry.is_dir()]

    def get_session(self, id: str) -> "SessionState":
        from common.config_loader import resolve_completion_config
        from server.application.domain.model.context_strategy import MessageRecord
        from server.application.domain.model.session import SessionState

        session_dir = self._path / id
        info_path = session_dir / SESSION_INFO
        msgs_path = session_dir / SESSION_MESSAGES

        try:
            with open(info_path) as f:
                raw_info = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File with part of session info not found: {info_path}") from e
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading session info file: {info_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in session info file: {info_path}") from e

        # Resolve file-referenced resources (system_prompt_path, output_config_path)
        # before validating, using the explicit helper instead of Pydantic context.
        base_dir = str(session_dir)
        if "completion_config" in raw_info:
            raw_info["completion_config"] = resolve_completion_config(raw_info["completion_config"], base_dir)
        if raw_info.get("message_context_strategy"):
            strat = raw_info["message_context_strategy"]
            if "completion_config" in strat:
                strat["completion_config"] = resolve_completion_config(strat["completion_config"], base_dir)

        info = SessionInfoDto.model_validate(raw_info)

        try:
            with open(msgs_path) as f:
                msgs = SessionMessagesDto.model_validate(json.load(f))
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File with part of session info not found: {msgs_path}") from e
        except PermissionError as e:
            raise PermissionError(f"Permission denied when reading session info file: {msgs_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in session info file: {msgs_path}") from e

        if info.message_context_strategy is None:
            raise ValueError(f"Session {id} is missing message context strategy metadata")

        records: list[MessageRecord] = [
            MessageRecord(
                id=_uuid.UUID(r.id),
                prev_id=_uuid.UUID(r.prev_id) if r.prev_id is not None else None,
                message=r.message,
            )
            for r in msgs.records
        ]

        return SessionState(
            id=info.id,
            created_at=info.created_at,
            completion_config=info.completion_config,
            statistics=info.statistics,
            strategy_type=info.message_context_strategy.type,
            strategy_metadata=info.message_context_strategy.metadata,
            strategy_completion_config=info.message_context_strategy.completion_config,
            strategy_records=records,
        )

    def _write_session_files(self, session_dir: Path, session: "Session") -> None:
        from common.config_loader import serialize_completion_config

        save_dir = str(session_dir)
        strategy = session.message_context_strategy

        info = SessionInfoDto(
            id=session.id,
            created_at=session.created_at,
            completion_config=session.completion_config,
            statistics=session.statistics.lifecycle_total_data or None,
            message_context_strategy=MessageContextStrategyInfoDto(
                type=strategy.strategy_type,
                metadata=strategy.get_metadata(),
                completion_config=strategy.completion_config,
            ),
        )
        msgs = SessionMessagesDto(
            records=[
                MessageRecordDto(
                    id=str(r.id),
                    prev_id=str(r.prev_id) if r.prev_id is not None else None,
                    message=r.message,
                )
                for r in strategy.get_history()
            ]
        )

        # Serialize to plain dicts, then apply file-writing serialization explicitly.
        info_data = info.model_dump(mode="json")
        info_data["completion_config"] = serialize_completion_config(session.completion_config, save_dir)
        if info_data.get("message_context_strategy"):
            info_data["message_context_strategy"]["completion_config"] = serialize_completion_config(
                strategy.completion_config, save_dir
            )

        try:
            with open(session_dir / SESSION_INFO, "w") as f:
                json.dump(info_data, f)
            with open(session_dir / SESSION_MESSAGES, "w") as f:
                json.dump(msgs.model_dump(mode="json"), f)
        except PermissionError as e:
            raise PermissionError(f"Permission denied when writing session files: {session_dir}") from e
        except OSError as e:
            raise OSError(f"Failed to write session files: {session_dir}") from e

    def create_session(self, session: "Session") -> None:
        session_dir = self._path / session.id
        try:
            session_dir.mkdir(exist_ok=False)
        except FileExistsError as e:
            raise FileExistsError(f"Session directory already exists: {session_dir}") from e
        self._write_session_files(session_dir, session)

    def update_session(self, session: "Session") -> None:
        session_dir = self._path / session.id
        if not session_dir.exists():
            raise FileNotFoundError(f"Session directory not found: {session_dir}")
        self._write_session_files(session_dir, session)

    def delete_session(self, id: str) -> None:
        session_dir = self._path / id
        try:
            shutil.rmtree(session_dir)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Session directory not found: {session_dir}") from e
        except PermissionError as e:
            raise PermissionError(f"Permission denied when deleting session directory: {session_dir}") from e
