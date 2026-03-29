import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import cast

from fastapi import APIRouter, HTTPException, Request, WebSocket

from server.adapter.inbound.web.error_handling import StorageError, handle_storage_errors
from server.adapter.inbound.web.http_schemas import (
    CreateSessionRequest,
    SessionDetail,
    SessionInfo,
    SessionSummary,
)
from server.application.domain.model.session import Session
from server.application.domain.service.create_session import CreateSessionUseCase
from server.application.domain.service.delete_session import DeleteSessionUseCase
from server.application.domain.service.get_session import GetSessionUseCase
from server.application.domain.service.list_sessions import ListSessionsUseCase

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Session connection registry (in-memory) ───────────────────────────────────

@dataclass
class SessionConnections:
    session: Session
    ws: WebSocket | None = None
    stream_task: asyncio.Task[None] | None = None


# ── Dependency helper ─────────────────────────────────────────────────────────

def _get_sessions(request: Request) -> dict[str, SessionConnections]:
    return cast("dict[str, SessionConnections]", request.app.state.sessions)


def _get_create_uc(request: Request) -> CreateSessionUseCase:
    return cast("CreateSessionUseCase", request.app.state.create_session_uc)


def _get_delete_uc(request: Request) -> DeleteSessionUseCase:
    return cast("DeleteSessionUseCase", request.app.state.delete_session_uc)


def _get_get_uc(request: Request) -> GetSessionUseCase:
    return cast("GetSessionUseCase", request.app.state.get_session_uc)


def _get_list_uc(request: Request) -> ListSessionsUseCase:
    return cast("ListSessionsUseCase", request.app.state.list_sessions_uc)


async def _get_or_load_session_connections(
    session_id: str,
    sessions: dict[str, SessionConnections],
    get_uc: GetSessionUseCase,
) -> SessionConnections:
    sc = sessions.get(session_id)
    if sc is not None:
        return sc
    try:
        with handle_storage_errors("Failed to load", session_id):
            session = await get_uc.execute(session_id)
            sc = SessionConnections(session=session)
            sessions[session_id] = sc
            return sc
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Session not found") from e
    except StorageError as e:
        raise HTTPException(status_code=500, detail="Could not read session data") from e


# ── Session management endpoints ──────────────────────────────────────────────

@router.post("/session", response_model=SessionSummary, status_code=201)
async def create_session(body: CreateSessionRequest, request: Request) -> SessionSummary:
    sessions = _get_sessions(request)
    create_uc = _get_create_uc(request)

    if body.session_id in sessions:
        raise HTTPException(status_code=409, detail="Session already exists")

    try:
        with handle_storage_errors("Failed to save", body.session_id):
            session = await create_uc.execute(body.session_id)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail="Session already exists on disk") from e
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {e.original}") from e

    sc = SessionConnections(session=session)
    sessions[body.session_id] = sc
    logger.info("Session created: %s", body.session_id)
    return SessionSummary(
        session_id=session.id,
        created_at=session.created_at,
        message_count=0,
    )


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request) -> None:
    sessions = _get_sessions(request)
    delete_uc = _get_delete_uc(request)

    sc = sessions.pop(session_id, None)
    if sc is not None and sc.ws is not None:
        with contextlib.suppress(Exception):
            await sc.ws.close(code=1001, reason="Session deleted")

    try:
        with handle_storage_errors("Failed to delete", session_id):
            delete_uc.execute(session_id)
    except FileNotFoundError:
        pass
    except StorageError as e:
        raise HTTPException(status_code=500, detail="Could not delete session data") from e

    logger.info("Session deleted: %s", session_id)


@router.get("/sessions", response_model=list[str])
async def list_sessions(request: Request) -> list[str]:
    list_uc = _get_list_uc(request)
    return list_uc.execute()


@router.get("/session/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, request: Request) -> SessionDetail:
    sessions = _get_sessions(request)
    get_uc = _get_get_uc(request)
    sc = await _get_or_load_session_connections(session_id, sessions, get_uc)
    return SessionDetail(
        id=sc.session.id,
        created_at=sc.session.created_at,
        completion_config=sc.session.completion_config,
        statistics=sc.session.statistics.lifecycle_total_data or None,
        messages=sc.session.messages,
    )


@router.get("/session/{session_id}/info", response_model=SessionInfo)
async def get_session_info(session_id: str, request: Request) -> SessionInfo:
    sessions = _get_sessions(request)
    get_uc = _get_get_uc(request)
    sc = await _get_or_load_session_connections(session_id, sessions, get_uc)
    return SessionInfo(
        id=sc.session.id,
        created_at=sc.session.created_at,
        completion_config=sc.session.completion_config,
        statistics=sc.session.statistics.lifecycle_total_data or None,
    )


@router.get("/session/{session_id}/messages")
async def get_session_messages(session_id: str, request: Request) -> list:
    sessions = _get_sessions(request)
    get_uc = _get_get_uc(request)
    sc = await _get_or_load_session_connections(session_id, sessions, get_uc)
    return sc.session.messages
