"""Unit tests for CreateSessionUseCase."""
import copy

import pytest

from server.application.domain.model.context_strategy import MessageContextStrategyDefaults
from server.application.domain.model.session import Session
from server.application.domain.service.create_session import CreateSessionUseCase

pytestmark = pytest.mark.asyncio


class TestCreateSessionUseCase:
    """CreateSessionUseCase creates a Session and persists it via the repository."""

    async def test_execute_returns_session_with_correct_id(
        self, mock_repository, mock_llm_factory, mock_billing_factory, completion_config,
        strategy_defaults, default_strategy_type
    ):
        use_case = CreateSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
            default_completion_config=copy.copy(completion_config),
            strategy_defaults=strategy_defaults,
            default_strategy_type=default_strategy_type,
        )

        session = await use_case.execute("my-session")

        assert isinstance(session, Session)
        assert session.id == "my-session"

    async def test_execute_persists_session_via_repository(
        self, mock_repository, mock_llm_factory, mock_billing_factory, completion_config,
        strategy_defaults, default_strategy_type
    ):
        use_case = CreateSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
            default_completion_config=copy.copy(completion_config),
            strategy_defaults=strategy_defaults,
            default_strategy_type=default_strategy_type,
        )

        await use_case.execute("session-abc")

        mock_repository.create_session.assert_called_once()
        saved_arg = mock_repository.create_session.call_args[0][0]
        assert isinstance(saved_arg, Session)
        assert saved_arg.id == "session-abc"

    async def test_execute_with_sliding_window_strategy(
        self, mock_repository, mock_llm_factory, mock_billing_factory, completion_config
    ):
        sw_defaults = {"sliding_window": MessageContextStrategyDefaults(
            type="sliding_window",
            completion_config=completion_config,
            metadata={"window_size": 4},
        )}
        use_case = CreateSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
            default_completion_config=copy.copy(completion_config),
            strategy_defaults=sw_defaults,
            default_strategy_type="sliding_window",
        )

        session = await use_case.execute("sliding-session")

        assert session.id == "sliding-session"
        mock_repository.create_session.assert_called_once()

    async def test_execute_saves_session_with_matching_strategy_type(
        self, mock_repository, mock_llm_factory, mock_billing_factory, completion_config,
        strategy_defaults, default_strategy_type
    ):
        use_case = CreateSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
            default_completion_config=copy.copy(completion_config),
            strategy_defaults=strategy_defaults,
            default_strategy_type=default_strategy_type,
        )

        await use_case.execute("s1")

        saved_arg = mock_repository.create_session.call_args[0][0]
        assert isinstance(saved_arg, Session)
        assert saved_arg.message_context_strategy.strategy_type == default_strategy_type

    async def test_execute_does_not_call_delete_or_update(
        self, mock_repository, mock_llm_factory, mock_billing_factory, completion_config,
        strategy_defaults, default_strategy_type
    ):
        use_case = CreateSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
            default_completion_config=copy.copy(completion_config),
            strategy_defaults=strategy_defaults,
            default_strategy_type=default_strategy_type,
        )

        await use_case.execute("s2")

        mock_repository.delete_session.assert_not_called()
        mock_repository.update_session.assert_not_called()

    async def test_execute_raises_for_unknown_strategy_type(
        self, mock_repository, mock_llm_factory, mock_billing_factory, completion_config,
        strategy_defaults
    ):
        use_case = CreateSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
            default_completion_config=copy.copy(completion_config),
            strategy_defaults=strategy_defaults,
            default_strategy_type="nonexistent_strategy",
        )

        with pytest.raises(ValueError, match="Unknown default strategy type"):
            await use_case.execute("s3")
