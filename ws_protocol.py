from __future__ import annotations
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field

from llm_adapter import StopReason, TokensUsage
from session import TokensCost


# ── Client → Server frames ────────────────────────────────────────────────────

class SendMessageFrame(BaseModel):
    type: Literal["send_message"] = "send_message"
    content: str


class CancelFrame(BaseModel):
    type: Literal["cancel"] = "cancel"


class PingFrame(BaseModel):
    type: Literal["ping"] = "ping"


ClientFrame = Annotated[
    Union[SendMessageFrame, CancelFrame, PingFrame],
    Field(discriminator="type"),
]


# ── Server → Client frames ────────────────────────────────────────────────────

class ChunkFrame(BaseModel):
    type: Literal["chunk"] = "chunk"
    delta: str


class DoneFrame(BaseModel):
    type: Literal["done"] = "done"
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tokens_usage: TokensUsage
    stop_reason: StopReason
    elapsed_s: int = Field(ge=0)
    tokens_cost: Optional[TokensCost] = None


class ErrorFrame(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class PongFrame(BaseModel):
    type: Literal["pong"] = "pong"


ServerFrame = Annotated[
    Union[ChunkFrame, DoneFrame, ErrorFrame, PongFrame],
    Field(discriminator="type"),
]
