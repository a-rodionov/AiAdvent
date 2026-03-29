"""Unit tests for DeleteSessionUseCase."""
import pytest

from server.application.domain.service.delete_session import DeleteSessionUseCase


class TestDeleteSessionUseCase:
    """DeleteSessionUseCase delegates directly to the repository port."""

    def test_execute_calls_repository_delete_with_correct_id(self, mock_repository):
        use_case = DeleteSessionUseCase(repository=mock_repository)

        use_case.execute("session-to-delete")

        mock_repository.delete_session.assert_called_once_with("session-to-delete")

    def test_execute_different_session_ids(self, mock_repository):
        use_case = DeleteSessionUseCase(repository=mock_repository)

        use_case.execute("abc")
        use_case.execute("xyz")

        assert mock_repository.delete_session.call_count == 2
        mock_repository.delete_session.assert_any_call("abc")
        mock_repository.delete_session.assert_any_call("xyz")

    def test_execute_does_not_call_other_repository_methods(self, mock_repository):
        use_case = DeleteSessionUseCase(repository=mock_repository)

        use_case.execute("s1")

        mock_repository.create_session.assert_not_called()
        mock_repository.update_session.assert_not_called()
        mock_repository.get_session.assert_not_called()
        mock_repository.get_session_ids.assert_not_called()

    def test_execute_propagates_repository_exception(self, mock_repository):
        mock_repository.delete_session.side_effect = FileNotFoundError("session not found")
        use_case = DeleteSessionUseCase(repository=mock_repository)

        with pytest.raises(FileNotFoundError, match="session not found"):
            use_case.execute("missing-session")
