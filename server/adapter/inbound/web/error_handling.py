"""Shared error-handling utilities for controllers (HTTP + WebSocket)."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when a storage operation fails due to OS/permission/data errors."""

    def __init__(self, message: str, original: Exception):
        super().__init__(message)
        self.original = original


@contextmanager
def handle_storage_errors(operation: str, session_id: str) -> Generator[None, None, None]:
    """Catch PermissionError / OSError / ValueError from storage
    operations, log them, and raise a single ``StorageError``.

    Parameters
    ----------
    operation:
        Human-readable label for the operation (used in the log message).
    session_id:
        The session identifier (used in the log message).
    """
    try:
        yield
    except FileNotFoundError:
        raise
    except FileExistsError:
        raise
    except (PermissionError, OSError, ValueError) as exc:
        logger.error(
            "%s session %s: %s", operation, session_id, exc,
        )
        raise StorageError(
            f"{operation} session {session_id}", exc,
        ) from exc
