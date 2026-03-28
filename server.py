import asyncio
import logging
import os
import sys
import time
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from any_llm import AuthenticationError, AnyLLMError
from dotenv import load_dotenv

from server_config import get_server_config
from completion_config import CompletionConfig, CompletionConfigFileAdapter, format_completion_config
from model_pricing import ModelPricing
from model_pricing_adapter import ModelPricingFileAdapter
from ws_protocol import (
    ClientFrame,
    SendMessageFrame, CancelFrame, PingFrame,
    ChunkFrame, DoneFrame, ErrorFrame, PongFrame,
)
from session import Session, SessionTextChunkEvent, SessionCompletionDoneEvent, TokensCost, SessionStatistics
from session_adapter import SessionFileAdapter
from llm_adapter import LlmAdapter, StopReason


STOP_REASON_DESCRIPTIONS = {
    StopReason.STOP: "The model reached a natural stopping point.",
    StopReason.LENGTH: "We exceeded the requested max_tokens or the model's maximum.",
    StopReason.TOOL_CALLS: "The model invoked one or more tools.",
    StopReason.CONTENT_FILTER: "When streaming classifiers intervene to handle potential policy violations.",
}


logger = logging.getLogger("server")

app = FastAPI(title="Chat Server")

# ── Application state (set in main before uvicorn.run) ───────────────────────

_sessions: dict[str, "SessionConnections"] = {}
_default_completion_config: Optional[CompletionConfig] = None
_model_pricing: Optional[ModelPricing] = None
_session_file_adapter: Optional[SessionFileAdapter] = None

_client_frame_adapter: TypeAdapter = TypeAdapter(ClientFrame)


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class SessionConnections:
    session: Session
    ws: Optional[WebSocket] = None
    stream_task: Optional[asyncio.Task] = None


# ── Request / response schemas ────────────────────────────────────────────────

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
    statistics: Optional[dict[str, SessionStatistics]] = None
    messages: list


class SessionInfo(BaseModel):
    id: str
    created_at: datetime
    completion_config: CompletionConfig
    statistics: Optional[dict[str, SessionStatistics]] = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _log_stats(label: str, stats: SessionStatistics) -> None:
    logger.info(label)
    for field, value in stats.tokens_usage.model_dump().items():
        logger.info(f"    {field}: {value}")
    if stats.tokens_cost is not None:
        for field, value in stats.tokens_cost.model_dump().items():
            logger.info(f"    {field} cost: ${value:.8f}")


async def _get_or_load_session_connections(session_id: str) -> "SessionConnections":
    session_connections = _sessions.get(session_id)
    if session_connections is not None:
        return session_connections
    try:
        session = Session.from_dto(
            LlmAdapter(_default_completion_config.provider),
            _model_pricing,
            _session_file_adapter.get_session(session_id),
        )
        session_connections = SessionConnections(session=session)
        _sessions[session_id] = session_connections
        return session_connections
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except PermissionError as e:
        logger.error("Permission error reading session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail="Could not read session data")
    except ValueError as e:
        logger.error("Corrupt session data for %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail="Session data is corrupt")


# ── Session management endpoints ──────────────────────────────────────────────

@app.post("/session", response_model=SessionSummary, status_code=201)
async def create_session(body: CreateSessionRequest) -> SessionSummary:
    if body.session_id in _sessions:
        raise HTTPException(status_code=409, detail="Session already exists")
    session_connections = SessionConnections(
        session=Session.create(
            llm=LlmAdapter(_default_completion_config.provider),
            id=body.session_id,
            model_pricing=_model_pricing,
            completion_config=_default_completion_config
        )
    )
    try:
        _session_file_adapter.create_session(session_connections.session.to_dto())
    except FileExistsError:
        raise HTTPException(status_code=409, detail="SessionConnections already exists on disk")
    except PermissionError as e:
        raise HTTPException(status_code=500, detail=f"Permission denied when saving session: {e}")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {e}")
    _sessions[body.session_id] = session_connections
    logger.info("Session created: %s", body.session_id)
    return SessionSummary(
        session_id=session_connections.session.id,
        created_at=session_connections.session.created_at,
        message_count=0,
    )


@app.delete("/session/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    session_connections = _sessions.pop(session_id, None)
    if session_connections is not None and session_connections.ws is not None:
        try:
            await session_connections.ws.close(code=1001, reason="Session deleted")
        except Exception:
            pass

    try:
        _session_file_adapter.delete_session(session_id)
    except PermissionError as e:
        logger.error("Permission error deleting session %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail="Could not delete session data")
    except FileNotFoundError:
        pass

    logger.info("Session deleted: %s", session_id)


@app.get("/sessions", response_model=list[str])
async def list_sessions() -> list[str]:
    return _session_file_adapter.get_session_ids()


@app.get("/session/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    sc = await _get_or_load_session_connections(session_id)
    return SessionDetail(
        id=sc.session.id,
        created_at=sc.session.created_at,
        completion_config=sc.session.completion_config,
        statistics=sc.session.statistics,
        messages=sc.session.messages,
    )


@app.get("/session/{session_id}/info", response_model=SessionInfo)
async def get_session_info(session_id: str) -> SessionInfo:
    sc = await _get_or_load_session_connections(session_id)
    return SessionInfo(
        id=sc.session.id,
        created_at=sc.session.created_at,
        completion_config=sc.session.completion_config,
        statistics=sc.session.statistics,
    )


@app.get("/session/{session_id}/messages")
async def get_session_messages(session_id: str) -> list:
    sc = await _get_or_load_session_connections(session_id)
    return sc.session.messages


# ── WebSocket streaming ───────────────────────────────────────────────────────

async def _stream_response(session_connections: SessionConnections, ws: WebSocket, content: str) -> None:
    try:
        async for event in session_connections.session.acompletion(content, is_stream_prefered=True):
            if isinstance(event, SessionTextChunkEvent):
                await ws.send_text(ChunkFrame(delta=event.text).model_dump_json())
            if isinstance(event, SessionCompletionDoneEvent):
                await ws.send_text(
                    DoneFrame(
                        provider=event.provider,
                        model=event.model,
                        tokens_usage=event.tokens_usage,
                        stop_reason=event.stop_reason,
                        elapsed_s=event.elapsed_s,
                        tokens_cost=event.tokens_cost,
                    ).model_dump_json()
                )

                description = STOP_REASON_DESCRIPTIONS.get(event.stop_reason, "Unknown stop reason.")
                logger.info("Response:")
                logger.info(f"    StopReason: {event.stop_reason}. {description}")
                logger.info(f"    Elapsed time: {event.elapsed_s:.0f}s")
                _log_stats("    Tokens usage:", SessionStatistics(
                    tokens_usage=event.tokens_usage,
                    tokens_cost=event.tokens_cost,
                ))

        if session_connections.session.statistics:
            logger.info("Session:")
            for key, stats in session_connections.session.statistics.items():
                provider, model = key.split(",", 1)
                _log_stats(f"  {provider}/{model}:", stats)

        try:
            _session_file_adapter.update_session(session_connections.session.to_dto())
        except PermissionError as e:
            logger.error("Permission denied persisting session %s: %s", session_connections.session.id, e)
        except OSError as e:
            logger.error("Failed to persist session %s: %s", session_connections.session.id, e)



    except asyncio.CancelledError:
        raise
    except AuthenticationError:
        try:
            await ws.send_text(
                ErrorFrame(
                    code="auth_error",
                    message="Authentication failed. Check ANTHROPIC_API_KEY.",
                ).model_dump_json()
            )
        except Exception:
            pass

    except AnyLLMError as e:
        try:
            await ws.send_text(
                ErrorFrame(code="api_error", message=str(e.message)).model_dump_json()
            )
        except Exception:
            pass


async def _ws_loop(session_connections: SessionConnections, ws: WebSocket) -> None:
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
            if session_connections.stream_task and not session_connections.stream_task.done():
                session_connections.stream_task.cancel()

        elif isinstance(frame, SendMessageFrame):
            if session_connections.stream_task and not session_connections.stream_task.done():
                await ws.send_text(
                    ErrorFrame(
                        code="stream_in_progress",
                        message="A stream is already in progress.",
                    ).model_dump_json()
                )
                continue

            session_connections.stream_task = asyncio.create_task(
                _stream_response(session_connections, ws, frame.content)
            )


@app.websocket("/session/{session_id}/ws")
async def session_ws(websocket: WebSocket, session_id: str) -> None:
    session_connections = _sessions.get(session_id)
    if session_connections is None:
        try:
            session = Session.from_dto(
                LlmAdapter(_default_completion_config.provider),
                _model_pricing,
                _session_file_adapter.get_session(session_id))
            session_connections = SessionConnections(session=session)
            _sessions[session_id] = session_connections
        except FileNotFoundError as e:
            logger.error("Session %s does not exist: %s", session_id, e)
            await websocket.accept()
            await websocket.close(code=4404, reason="Session not found")
            return
        except (PermissionError, OSError, ValueError) as e:
            logger.error("Failed to load session %s from disk: %s", session_id, e)
            await websocket.accept()
            await websocket.close(code=4500, reason="Failed to load session")
            return

    if session_connections.ws is not None:
        await websocket.accept()
        await websocket.close(code=4409, reason="Session already has an active connection")
        return

    await websocket.accept()
    session_connections.ws = websocket

    logger.info("WebSocket connected: session=%s", session_id)

    try:
        await _ws_loop(session_connections, websocket)
    except WebSocketDisconnect:
        pass
    finally:
        if session_connections.stream_task and not session_connections.stream_task.done():
            session_connections.stream_task.cancel()
            try:
                await session_connections.stream_task
            except (asyncio.CancelledError, Exception):
                pass
        session_connections.ws = None
        session_connections.stream_task = None
        logger.info("WebSocket disconnected: session=%s", session_id)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    from pathlib import Path
    global _default_completion_config, _model_pricing, _session_file_adapter

    parser = argparse.ArgumentParser(
        prog="server",
        description="Chat server.",
    )
    parser.add_argument("server_config", metavar="SERVER_CONFIG_FILE")
    
    args = parser.parse_args()
    server_config = get_server_config(args.server_config)
    load_dotenv()

    logging.basicConfig(
        level=getattr(logging, server_config.log_level.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    _default_completion_config = CompletionConfigFileAdapter(server_config.default_completion_config_path).create_completion_config()
    _model_pricing = ModelPricing.from_dtos(
        ModelPricingFileAdapter(server_config.models_pricing_path).get_all_pricing_dtos())
    Path(server_config.session_storage_dir).mkdir(parents=True, exist_ok=True)
    _session_file_adapter = SessionFileAdapter(server_config.session_storage_dir)

    os.environ.setdefault("ANY_LLM_UNIFIED_EXCEPTIONS", "1")

    logger.info(format_completion_config(_default_completion_config))

    uvicorn.run(app, host=server_config.host, port=server_config.port)


if __name__ == "__main__":
    main()
