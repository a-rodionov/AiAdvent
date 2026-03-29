from datetime import datetime

from pydantic import BaseModel, Field

from server.application.domain.model.completion import CompletionConfig


class CreateSessionRequest(BaseModel):
    session_id: str = Field(min_length=1)


class SessionSummary(BaseModel):
    session_id: str
    created_at: datetime
    message_count: int


class SessionDetail(BaseModel):
    id: str
    created_at: datetime
    completion_config: CompletionConfig
    statistics: dict | None = None
    messages: list


class SessionInfo(BaseModel):
    id: str
    created_at: datetime
    completion_config: CompletionConfig
    statistics: dict | None = None
