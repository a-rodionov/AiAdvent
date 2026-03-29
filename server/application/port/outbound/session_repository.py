from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.application.domain.model.session import Session, SessionState


class ISessionRepository(ABC):
    @abstractmethod
    def get_session_ids(self) -> list[str]: ...

    @abstractmethod
    def get_session(self, id: str) -> SessionState: ...

    @abstractmethod
    def create_session(self, session: Session) -> None: ...

    @abstractmethod
    def update_session(self, session: Session) -> None: ...

    @abstractmethod
    def delete_session(self, id: str) -> None: ...
