from server.application.port.outbound.session_repository import ISessionRepository


class ListSessionsUseCase:
    def __init__(self, repository: ISessionRepository) -> None:
        self._repository = repository

    def execute(self) -> list[str]:
        return self._repository.get_session_ids()
