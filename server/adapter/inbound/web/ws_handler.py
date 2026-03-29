import asyncio
import contextlib
import logging

from any_llm import AnyLLMError, AuthenticationError
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from server.adapter.inbound.web.error_handling import StorageError, handle_storage_errors
from server.adapter.inbound.web.session_routes import SessionConnections
from server.adapter.inbound.web.ws_protocol import (
    CancelFrame,
    ChunkFrame,
    ClientFrame,
    DoneFrame,
    ErrorFrame,
    PingFrame,
    PongFrame,
    SendMessageFrame,
)
from server.application.domain.model.session import SessionCompletionDoneEvent, SessionTextChunkEvent, StopReason
from server.application.domain.model.usage_stats import ModelStats
from server.application.domain.service.get_session import GetSessionUseCase
from server.application.domain.service.send_message import SendMessageUseCase

logger = logging.getLogger(__name__)

_client_frame_adapter: TypeAdapter = TypeAdapter(ClientFrame)

STOP_REASON_DESCRIPTIONS = {
    StopReason.STOP: "The model reached a natural stopping point.",
    StopReason.LENGTH: "We exceeded the requested max_tokens or the model's maximum.",
    StopReason.TOOL_CALLS: "The model invoked one or more tools.",
    StopReason.CONTENT_FILTER: "When streaming classifiers intervene to handle potential policy violations.",
}


def _log_stats(label: str, stats: ModelStats) -> None:
    logger.info(label)
    for field_name, value in stats.usage.model_dump().items():
        logger.info(f"    {field_name}: {value}")
    if stats.cost is not None:
        for field_name, value in stats.cost.model_dump().items():
            logger.info(f"    {field_name} cost: ${value:.8f}")


async def _stream_response(
    sc: SessionConnections,
    ws: WebSocket,
    content: str,
    send_message_uc: SendMessageUseCase,
) -> None:
    try:
        async for event in send_message_uc.execute(sc.session, content, is_stream_prefered=True):
            if isinstance(event, SessionTextChunkEvent):
                await ws.send_text(ChunkFrame(delta=event.text).model_dump_json())
            if isinstance(event, SessionCompletionDoneEvent):
                if event.statistics:
                    for provider, model_stats in event.statistics.items():
                        for model, stats in model_stats.items():
                            await ws.send_text(
                                DoneFrame(
                                    provider=provider,
                                    model=model,
                                    tokens_usage=stats.usage,
                                    stop_reason=event.stop_reason,
                                    elapsed_s=event.elapsed_s,
                                    tokens_cost=stats.cost,
                                ).model_dump_json()
                            )

                description = STOP_REASON_DESCRIPTIONS.get(event.stop_reason, "Unknown stop reason.")
                logger.info("Response:")
                logger.info(f"    StopReason: {event.stop_reason}. {description}")
                logger.info(f"    Elapsed time: {event.elapsed_s:.0f}s")
                if event.statistics:
                    for provider, model_stats in event.statistics.items():
                        for model, stats in model_stats.items():
                            _log_stats(f"    {provider}/{model}:", stats)

        if sc.session.statistics:
            logger.info("Session:")
            for provider, model_stats in sc.session.statistics.lifecycle_total_data.items():
                for model, stats in model_stats.items():
                    _log_stats(f"  {provider}/{model}:", stats)

    except asyncio.CancelledError:
        raise
    except AuthenticationError:
        with contextlib.suppress(Exception):
            await ws.send_text(
                ErrorFrame(
                    code="auth_error",
                    message="Authentication failed. Check ANTHROPIC_API_KEY.",
                ).model_dump_json()
            )

    except AnyLLMError as e:
        with contextlib.suppress(Exception):
            await ws.send_text(
                ErrorFrame(code="api_error", message=str(e.message)).model_dump_json()
            )


async def _ws_loop(sc: SessionConnections, ws: WebSocket, send_message_uc: SendMessageUseCase) -> None:
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
            if sc.stream_task and not sc.stream_task.done():
                sc.stream_task.cancel()

        elif isinstance(frame, SendMessageFrame):
            if sc.stream_task and not sc.stream_task.done():
                await ws.send_text(
                    ErrorFrame(
                        code="stream_in_progress",
                        message="A stream is already in progress.",
                    ).model_dump_json()
                )
                continue

            sc.stream_task = asyncio.create_task(
                _stream_response(sc, ws, frame.content, send_message_uc)
            )


async def handle_ws(
    websocket: WebSocket,
    session_id: str,
    sessions: dict,
    get_uc: GetSessionUseCase,
    send_message_uc: SendMessageUseCase,
) -> None:
    sc = sessions.get(session_id)
    if sc is None:
        try:
            with handle_storage_errors("Failed to load", session_id):
                session = await get_uc.execute(session_id)
                sc = SessionConnections(session=session)
                sessions[session_id] = sc
        except FileNotFoundError as e:
            logger.error("Session %s does not exist: %s", session_id, e)
            await websocket.accept()
            await websocket.close(code=4404, reason="Session not found")
            return
        except StorageError:
            await websocket.accept()
            await websocket.close(code=4500, reason="Failed to load session")
            return

    if sc.ws is not None:
        await websocket.accept()
        await websocket.close(code=4409, reason="Session already has an active connection")
        return

    await websocket.accept()
    sc.ws = websocket

    logger.info("WebSocket connected: session=%s", session_id)

    try:
        await _ws_loop(sc, websocket, send_message_uc)
    except WebSocketDisconnect:
        pass
    finally:
        if sc.stream_task and not sc.stream_task.done():
            sc.stream_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await sc.stream_task
        sc.ws = None
        sc.stream_task = None
        logger.info("WebSocket disconnected: session=%s", session_id)
