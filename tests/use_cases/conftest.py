"""Shared fixtures for use case unit tests.

All mocks target the abstract ports (ILlmPort, ISessionRepository), keeping
tests isolated from any concrete adapter implementation — the hexagonal
architecture's key testability benefit.
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.context_strategy import MessageContextStrategyDefaults
from server.application.domain.model.model_billing import ModelBilling
from server.application.domain.model.session import SessionState, StopReason
from server.application.domain.model.usage_stats import TokensUsage
from server.application.port.outbound.llm_port import CompletionDoneEvent, ILlmPort, TextChunkEvent
from server.application.port.outbound.llm_port_factory import ILlmPortFactory
from server.application.port.outbound.model_billing_factory import IModelBillingFactory
from server.application.port.outbound.session_repository import ISessionRepository

# ── Port mocks ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_repository():
    repo = MagicMock(spec=ISessionRepository)
    repo.get_session_ids.return_value = []
    return repo


@pytest.fixture
def mock_llm():
    """LLM port mock that yields a single text chunk then a done event."""
    llm = MagicMock(spec=ILlmPort)

    async def _acompletion(full_messages, completion_config, is_stream_prefered):
        yield TextChunkEvent(text="Hello, world!")
        yield CompletionDoneEvent(
            provider="test_provider",
            model="test_model",
            tokens_usage=TokensUsage(prompt_tokens=10, completion_tokens=5),
            stop_reason=StopReason.STOP,
            elapsed_s=1,
        )

    llm.acompletion = _acompletion
    return llm


@pytest.fixture
def mock_llm_factory(mock_llm):
    """LLM port factory mock that always returns the same mock LLM."""
    factory = MagicMock(spec=ILlmPortFactory)
    factory.create.return_value = mock_llm
    return factory


@pytest.fixture
def mock_billing_factory():
    """Model billing factory mock that always returns None (no pricing)."""
    factory = MagicMock(spec=IModelBillingFactory)
    factory.create.return_value = None
    return factory


# ── Value object fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def completion_config():
    return CompletionConfig(provider="test_provider", model="test_model", max_tokens=100)


@pytest.fixture
def strategy_defaults(completion_config):
    return {"dummy": MessageContextStrategyDefaults(type="dummy", completion_config=completion_config)}


@pytest.fixture
def default_strategy_type():
    return "dummy"


@pytest.fixture
def model_billing():
    return ModelBilling(
        tokens_per_price=1_000_000,
        base_input_tokens=3.0,
        output_tokens=15.0,
    )


@pytest.fixture
def session_state(completion_config):
    """A minimal SessionState suitable for repository stubs."""
    return SessionState(
        id="test-session-id",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        completion_config=completion_config,
        statistics=None,
        strategy_type="dummy",
        strategy_metadata={},
        strategy_completion_config=completion_config,
        strategy_records=[],
    )
