from collections.abc import AsyncGenerator

from server.application.domain.model.session import Session, SessionEvent
from server.application.port.outbound.session_repository import ISessionRepository


class SendMessageUseCase:
    def __init__(self, repository: ISessionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        session: Session,
        prompt: str,
        is_stream_prefered: bool,
    ) -> AsyncGenerator[SessionEvent, None]:
        async for event in session.acompletion(prompt, is_stream_prefered):
            yield event
        self._repository.update_session(session)
