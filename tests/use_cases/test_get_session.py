"""Unit tests for GetSessionUseCase."""
import pytest

from server.application.domain.model.session import Session
from server.application.domain.service.get_session import GetSessionUseCase

pytestmark = pytest.mark.asyncio


class TestGetSessionUseCase:
    """GetSessionUseCase loads a SessionState from the repository and hydrates a Session domain object."""

    async def test_execute_returns_session_for_existing_id(
        self, mock_repository, mock_llm_factory, mock_billing_factory, session_state
    ):
        mock_repository.get_session.return_value = session_state
        use_case = GetSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
        )

        session = await use_case.execute("test-session-id")

        assert isinstance(session, Session)
        assert session.id == "test-session-id"

    async def test_execute_queries_repository_with_correct_id(
        self, mock_repository, mock_llm_factory, mock_billing_factory, session_state
    ):
        mock_repository.get_session.return_value = session_state
        use_case = GetSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
        )

        await use_case.execute("test-session-id")

        mock_repository.get_session.assert_called_once_with("test-session-id")

    async def test_execute_restores_session_created_at(
        self, mock_repository, mock_llm_factory, mock_billing_factory, session_state
    ):
        mock_repository.get_session.return_value = session_state
        use_case = GetSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
        )

        session = await use_case.execute("test-session-id")

        assert session.created_at == session_state.created_at

    async def test_execute_propagates_repository_exception(
        self, mock_repository, mock_llm_factory, mock_billing_factory
    ):
        mock_repository.get_session.side_effect = KeyError("session-missing")
        use_case = GetSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
        )

        with pytest.raises(KeyError):
            await use_case.execute("session-missing")

    async def test_execute_does_not_call_other_repository_methods(
        self, mock_repository, mock_llm_factory, mock_billing_factory, session_state
    ):
        mock_repository.get_session.return_value = session_state
        use_case = GetSessionUseCase(
            repository=mock_repository,
            llm_factory=mock_llm_factory,
            model_billing_factory=mock_billing_factory,
        )

        await use_case.execute("test-session-id")

        mock_repository.create_session.assert_not_called()
        mock_repository.update_session.assert_not_called()
        mock_repository.delete_session.assert_not_called()
