from server.application.port.outbound.session_repository import ISessionRepository


class DeleteSessionUseCase:
    def __init__(self, repository: ISessionRepository) -> None:
        self._repository = repository

    def execute(self, session_id: str) -> None:
        self._repository.delete_session(session_id)
