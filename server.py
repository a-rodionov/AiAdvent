import asyncio
import logging
import os
import sys
import time
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from anthropic import AsyncAnthropic, APIError, AuthenticationError, transform_schema
from dotenv import load_dotenv

from server_config import ServerConfigFileAdapter, format_server_config
from conversation_config import ConversationConfig, ConversationConfigFileAdapter, format_conversation_config
from model_pricing import ModelPricing, ModelPricingFileAdapter, format_pricing_report
from ws_protocol import (
    ClientFrame,
    SendMessageFrame, CancelFrame, PingFrame,
    ChunkFrame, DoneFrame, ErrorFrame, PongFrame,
)

logger = logging.getLogger("server")

app = FastAPI(title="Chat Server")

# ── Application state (set in main before uvicorn.run) ───────────────────────

_sessions: dict[str, "Session"] = {}
_conversation_config: Optional[ConversationConfig] = None
_model_pricing_file_adapter: Optional[ModelPricingFileAdapter] = None
_anthropic_client: Optional[AsyncAnthropic] = None

_client_frame_adapter: TypeAdapter = TypeAdapter(ClientFrame)


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class Session:
    id: str
    created_at: datetime
    messages: list = field(default_factory=list)
    model_pricing: Optional[ModelPricing] = None
    ws: Optional[WebSocket] = None
    stream_task: Optional[asyncio.Task] = None
    stream_committed: bool = False


# ── Request / response schemas ────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    session_id: str = Field(min_length=1)


class SessionSummary(BaseModel):
    session_id: str
    created_at: datetime
    message_count: int


class MessageRecord(BaseModel):
    role: str
    content: str


class SessionDetail(BaseModel):
    session_id: str
    created_at: datetime
    message_count: int
    messages: list[MessageRecord]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_kwargs(config: ConversationConfig, messages: list) -> dict:
    """Build Anthropic API kwargs from conversation config."""
    kwargs: dict = {
        "max_tokens": config.max_tokens,
        "messages": messages,
        "model": config.model,
    }
    if config.system_prompt:
        kwargs["system"] = config.system_prompt
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    if config.top_k is not None:
        kwargs["top_k"] = config.top_k
    if config.temperature is None and config.top_p is not None:
        kwargs["top_p"] = config.top_p
    if config.stop_sequences is not None:
        kwargs["stop_sequences"] = config.stop_sequences
    if config.output_config is not None:
        kwargs["output_config"] = {
            "format": {
                "type": "json_schema",
                "schema": transform_schema(config.output_config.json_schema),
            }
        }
    return kwargs


def _log_turn(session: Session, message, start_time: float) -> None:
    elapsed_s = (time.monotonic() - start_time)
    if session.model_pricing:
        session.model_pricing.estimate(
            base_input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
        logger.info(
            "Session %s: stop=%s elapsed=%.0fs\n%s",
            session.id,
            message.stop_reason,
            elapsed_s,
            format_pricing_report(session.model_pricing.get_report()),
        )
    else:
        logger.info(
            "Session %s: stop=%s elapsed=%.0fs input tokens=%d output tokens=%d",
            session.id,
            message.stop_reason,
            elapsed_s,
            message.usage.input_tokens,
            message.usage.output_tokens,
        )


# ── Session management endpoints ──────────────────────────────────────────────

@app.post("/session", response_model=SessionSummary, status_code=201)
async def create_session(body: CreateSessionRequest) -> SessionSummary:
    if body.session_id in _sessions:
        raise HTTPException(status_code=409, detail="Session already exists")
    model_pricing = None
    if _model_pricing_file_adapter is not None and _conversation_config is not None:
        model_pricing = _model_pricing_file_adapter.create_model_pricing(_conversation_config.model)
    session = Session(
        id=body.session_id,
        created_at=datetime.now(tz=timezone.utc),
        model_pricing=model_pricing,
    )
    _sessions[body.session_id] = session
    logger.info("Session created: %s", body.session_id)
    return SessionSummary(
        session_id=session.id,
        created_at=session.created_at,
        message_count=0,
    )


@app.delete("/session/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    session = _sessions.pop(session_id, None)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.ws is not None:
        try:
            await session.ws.close(code=1001, reason="Session deleted")
        except Exception:
            pass
    logger.info("Session deleted: %s", session_id)


@app.get("/sessions", response_model=list[SessionSummary])
async def list_sessions() -> list[SessionSummary]:
    return [
        SessionSummary(
            session_id=s.id,
            created_at=s.created_at,
            message_count=len(s.messages),
        )
        for s in _sessions.values()
    ]


@app.get("/session/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetail(
        session_id=session.id,
        created_at=session.created_at,
        message_count=len(session.messages),
        messages=[MessageRecord(**m) for m in session.messages],
    )


# ── WebSocket streaming ───────────────────────────────────────────────────────

async def _stream_response(session: Session, ws: WebSocket, content: str) -> None:
    session.messages.append({"role": "user", "content": content})
    session.stream_committed = False
    kwargs = _build_kwargs(_conversation_config, session.messages)

    try:
        assistant_text = ""
        start_time = time.monotonic()
        async with _anthropic_client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                assistant_text += text
                await ws.send_text(ChunkFrame(delta=text).model_dump_json())
            message = await stream.get_final_message()

        session.messages.append({"role": "assistant", "content": assistant_text})
        session.stream_committed = True

        await ws.send_text(
            DoneFrame(
                stop_reason=message.stop_reason,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
            ).model_dump_json()
        )

        _log_turn(session, message, start_time)

    except asyncio.CancelledError:
        if not session.stream_committed:
            session.messages.pop()
        raise

    except AuthenticationError:
        session.messages.pop()
        try:
            await ws.send_text(
                ErrorFrame(
                    code="auth_error",
                    message="Authentication failed. Check ANTHROPIC_API_KEY.",
                ).model_dump_json()
            )
        except Exception:
            pass

    except APIError as e:
        session.messages.pop()
        try:
            await ws.send_text(
                ErrorFrame(code="api_error", message=str(e.message)).model_dump_json()
            )
        except Exception:
            pass


async def _ws_loop(session: Session, ws: WebSocket) -> None:
    while True:
        raw = await ws.receive_text()

        try:
            frame = _client_frame_adapter.validate_json(raw)
        except ValidationError:
            await ws.send_text(
                ErrorFrame(
                    code="invalid_frame",
                    message="Could not parse client frame.",
                ).model_dump_json()
            )
            continue

        if isinstance(frame, PingFrame):
            await ws.send_text(PongFrame().model_dump_json())

        elif isinstance(frame, CancelFrame):
            if session.stream_task and not session.stream_task.done():
                session.stream_task.cancel()

        elif isinstance(frame, SendMessageFrame):
            if session.stream_task and not session.stream_task.done():
                await ws.send_text(
                    ErrorFrame(
                        code="stream_in_progress",
                        message="A stream is already in progress.",
                    ).model_dump_json()
                )
                continue

            session.stream_task = asyncio.create_task(
                _stream_response(session, ws, frame.content)
            )


@app.websocket("/session/{session_id}/ws")
async def session_ws(websocket: WebSocket, session_id: str) -> None:
    session = _sessions.get(session_id)
    if session is None:
        await websocket.accept()
        await websocket.close(code=4404, reason="Session not found")
        return

    if session.ws is not None:
        await websocket.accept()
        await websocket.close(code=4409, reason="Session already has an active connection")
        return

    await websocket.accept()
    session.ws = websocket

    logger.info("WebSocket connected: session=%s", session_id)

    try:
        await _ws_loop(session, websocket)
    except WebSocketDisconnect:
        pass
    finally:
        if session.stream_task and not session.stream_task.done():
            session.stream_task.cancel()
            try:
                await session.stream_task
            except (asyncio.CancelledError, Exception):
                pass
        session.ws = None
        session.stream_task = None
        logger.info("WebSocket disconnected: session=%s", session_id)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    global _conversation_config, _model_pricing_file_adapter, _anthropic_client

    parser = argparse.ArgumentParser(
        prog="server",
        description="Chat server.",
    )
    parser.add_argument("server_config", metavar="SERVER_CONFIG_FILE")
    args = parser.parse_args()
    server_config = ServerConfigFileAdapter(args.server_config).create_server_config()
    logging.basicConfig(
        level=getattr(logging, server_config.log_level.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.critical("ANTHROPIC_API_KEY environment variable is not set.")
        sys.exit(1)

    _conversation_config = ConversationConfigFileAdapter(
        server_config.default_conversation_config_path
    ).create_conversation_config()
    _model_pricing_file_adapter = ModelPricingFileAdapter(server_config.models_pricing_path)
    _anthropic_client = AsyncAnthropic(api_key=api_key)

    logger.info(format_server_config(server_config))
    logger.info(format_conversation_config(_conversation_config))

    uvicorn.run(app, host=server_config.host, port=server_config.port)


if __name__ == "__main__":
    main()
