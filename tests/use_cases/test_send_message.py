"""Unit tests for SendMessageUseCase."""
from unittest.mock import MagicMock

import pytest

from server.application.domain.model.session import SessionCompletionDoneEvent, SessionTextChunkEvent, StopReason
from server.application.domain.service.send_message import SendMessageUseCase

pytestmark = pytest.mark.asyncio


def _make_session(events):
    """Build a minimal Session mock whose acompletion yields the given events."""
    session = MagicMock()
    session.to_dto.return_value = MagicMock()

    async def _acompletion(prompt, is_stream_prefered):
        for event in events:
            yield event

    session.acompletion = _acompletion
    return session


class TestSendMessageUseCase:
    """SendMessageUseCase streams events from Session and persists state afterwards."""

    async def test_execute_yields_text_chunk_events(self, mock_repository):
        chunk = SessionTextChunkEvent(text="Hello!")
        done = SessionCompletionDoneEvent(stop_reason=StopReason.STOP, elapsed_s=1)
        session = _make_session([chunk, done])
        use_case = SendMessageUseCase(repository=mock_repository)

        events = [e async for e in use_case.execute(session, "Hi", False)]

        text_chunks = [e for e in events if isinstance(e, SessionTextChunkEvent)]
        assert len(text_chunks) == 1
        assert text_chunks[0].text == "Hello!"

    async def test_execute_yields_done_event(self, mock_repository):
        done = SessionCompletionDoneEvent(stop_reason=StopReason.STOP, elapsed_s=2)
        session = _make_session([done])
        use_case = SendMessageUseCase(repository=mock_repository)

        events = [e async for e in use_case.execute(session, "ping", False)]

        done_events = [e for e in events if isinstance(e, SessionCompletionDoneEvent)]
        assert len(done_events) == 1
        assert done_events[0].stop_reason == StopReason.STOP

    async def test_execute_yields_all_events_in_order(self, mock_repository):
        chunk1 = SessionTextChunkEvent(text="foo")
        chunk2 = SessionTextChunkEvent(text="bar")
        done = SessionCompletionDoneEvent(stop_reason=StopReason.STOP, elapsed_s=0)
        session = _make_session([chunk1, chunk2, done])
        use_case = SendMessageUseCase(repository=mock_repository)

        events = [e async for e in use_case.execute(session, "prompt", True)]

        assert len(events) == 3
        assert events[0].text == "foo"
        assert events[1].text == "bar"
        assert isinstance(events[2], SessionCompletionDoneEvent)

    async def test_execute_updates_session_in_repository_after_completion(
        self, mock_repository
    ):
        done = SessionCompletionDoneEvent(stop_reason=StopReason.STOP, elapsed_s=0)
        session = _make_session([done])
        use_case = SendMessageUseCase(repository=mock_repository)

        # Consume the full generator
        async for _ in use_case.execute(session, "question", False):
            pass

        mock_repository.update_session.assert_called_once()

    async def test_execute_passes_session_to_repository(self, mock_repository):
        done = SessionCompletionDoneEvent(stop_reason=StopReason.STOP, elapsed_s=0)
        session = _make_session([done])
        use_case = SendMessageUseCase(repository=mock_repository)

        async for _ in use_case.execute(session, "q", False):
            pass

        mock_repository.update_session.assert_called_once_with(session)

    async def test_execute_does_not_update_repository_before_generator_exhausted(
        self, mock_repository
    ):
        chunk = SessionTextChunkEvent(text="partial")
        done = SessionCompletionDoneEvent(stop_reason=StopReason.STOP, elapsed_s=0)
        session = _make_session([chunk, done])
        use_case = SendMessageUseCase(repository=mock_repository)

        gen = use_case.execute(session, "q", False)
        # Consume only the first event — repository must not have been called yet
        await gen.__anext__()

        mock_repository.update_session.assert_not_called()

    async def test_execute_with_no_events_still_updates_repository(self, mock_repository):
        session = _make_session([])
        use_case = SendMessageUseCase(repository=mock_repository)

        async for _ in use_case.execute(session, "q", False):
            pass

        mock_repository.update_session.assert_called_once()
