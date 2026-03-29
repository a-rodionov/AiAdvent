import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket

from server.adapter.inbound.web.session_routes import router as session_router
from server.adapter.inbound.web.ws_handler import handle_ws
from server.adapter.outbound.llm.llm_port_factory_adapter import LlmPortFactoryAdapter
from server.adapter.outbound.persistence.model_billing_factory_adapter import ModelBillingFactoryAdapter
from server.adapter.outbound.persistence.session_file_adapter import SessionFileAdapter
from server.application.domain.service.create_session import CreateSessionUseCase
from server.application.domain.service.delete_session import DeleteSessionUseCase
from server.application.domain.service.get_session import GetSessionUseCase
from server.application.domain.service.list_sessions import ListSessionsUseCase
from server.application.domain.service.send_message import SendMessageUseCase
from server.common.config_loader import ServerConfig, load_message_context_strategies

logger = logging.getLogger(__name__)


def create_app(server_config: ServerConfig) -> FastAPI:
    """Wire all dependencies and return a configured FastAPI application."""

    # ── Infrastructure / adapters ─────────────────────────────────────────────
    llm_factory = LlmPortFactoryAdapter()

    Path(server_config.session_storage_path).mkdir(parents=True, exist_ok=True)
    repository = SessionFileAdapter(server_config.session_storage_path)

    model_billing_factory = ModelBillingFactoryAdapter(server_config.models_billing_path)

    configs_dir = str(Path(server_config.message_context_strategies_path).parent.resolve())
    strategy_defaults = load_message_context_strategies(
        server_config.message_context_strategies_path, configs_dir
    )

    # ── Use cases ─────────────────────────────────────────────────────────────
    create_session_uc = CreateSessionUseCase(
        repository=repository,
        llm_factory=llm_factory,
        model_billing_factory=model_billing_factory,
        default_completion_config=server_config.default_completion_config,
        strategy_defaults=strategy_defaults,
        default_strategy_type=server_config.default_message_context_strategy,
    )
    get_session_uc = GetSessionUseCase(
        repository=repository,
        llm_factory=llm_factory,
        model_billing_factory=model_billing_factory,
    )
    delete_session_uc = DeleteSessionUseCase(repository=repository)
    list_sessions_uc = ListSessionsUseCase(repository=repository)
    send_message_uc = SendMessageUseCase(repository=repository)

    # ── FastAPI application ───────────────────────────────────────────────────
    app = FastAPI(title="Chat Server")

    # In-memory session connection registry (shared across requests via app.state)
    app.state.sessions = {}
    app.state.create_session_uc = create_session_uc
    app.state.get_session_uc = get_session_uc
    app.state.delete_session_uc = delete_session_uc
    app.state.list_sessions_uc = list_sessions_uc
    app.state.send_message_uc = send_message_uc

    # ── HTTP routes ───────────────────────────────────────────────────────────
    app.include_router(session_router)

    # ── WebSocket endpoint ────────────────────────────────────────────────────
    @app.websocket("/session/{session_id}/ws")
    async def session_ws(websocket: WebSocket, session_id: str) -> None:
        await handle_ws(
            websocket=websocket,
            session_id=session_id,
            sessions=app.state.sessions,
            get_uc=app.state.get_session_uc,
            send_message_uc=app.state.send_message_uc,
        )

    return app
