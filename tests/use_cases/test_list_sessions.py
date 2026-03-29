"""Unit tests for ListSessionsUseCase."""
import pytest

from server.application.domain.service.list_sessions import ListSessionsUseCase


class TestListSessionsUseCase:
    """ListSessionsUseCase is a thin pass-through to the repository port."""

    def test_execute_returns_empty_list_when_no_sessions(self, mock_repository):
        mock_repository.get_session_ids.return_value = []
        use_case = ListSessionsUseCase(repository=mock_repository)

        result = use_case.execute()

        assert result == []

    def test_execute_returns_all_session_ids(self, mock_repository):
        mock_repository.get_session_ids.return_value = ["s1", "s2", "s3"]
        use_case = ListSessionsUseCase(repository=mock_repository)

        result = use_case.execute()

        assert result == ["s1", "s2", "s3"]

    def test_execute_calls_repository_exactly_once(self, mock_repository):
        use_case = ListSessionsUseCase(repository=mock_repository)

        use_case.execute()

        mock_repository.get_session_ids.assert_called_once()

    def test_execute_does_not_call_other_repository_methods(self, mock_repository):
        use_case = ListSessionsUseCase(repository=mock_repository)

        use_case.execute()

        mock_repository.get_session.assert_not_called()
        mock_repository.create_session.assert_not_called()
        mock_repository.update_session.assert_not_called()
        mock_repository.delete_session.assert_not_called()

    def test_execute_propagates_repository_exception(self, mock_repository):
        mock_repository.get_session_ids.side_effect = OSError("storage unavailable")
        use_case = ListSessionsUseCase(repository=mock_repository)

        with pytest.raises(OSError, match="storage unavailable"):
            use_case.execute()
