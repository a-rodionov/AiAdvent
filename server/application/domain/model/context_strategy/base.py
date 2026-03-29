"""Base types and abstract base class for message context strategies.

Spec: ``openspec/specs/message-context-strategy/spec.md``
"""
from __future__ import annotations

import uuid as _uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, NamedTuple
from uuid import UUID

from pydantic import BaseModel, Field

from server.application.domain.model.completion import CompletionConfig

if TYPE_CHECKING:
    from server.application.port.outbound.llm_port import ILlmPort


class MessageContextStrategyDefaults(BaseModel):
    type: str = Field(min_length=1)
    completion_config: CompletionConfig
    metadata: dict = Field(default_factory=dict)


class MessageRecord(NamedTuple):
    id: UUID
    prev_id: UUID | None
    message: dict[str, str]


class MessageContextStrategy(ABC):
    def __init__(self, llm: ILlmPort, completion_config: CompletionConfig, records: list[MessageRecord] | None = None):
        self._llm: ILlmPort = llm
        self._completion_config = completion_config
        self._records: list[MessageRecord] = list(records) if records else []

    async def add_user_query(self, content: str) -> None:
        prev_id = self._records[-1].id if self._records else None
        self._records.append(MessageRecord(
            id=_uuid.uuid4(),
            prev_id=prev_id,
            message={"role": "user", "content": content},
        ))

    async def add_model_response(self, content: str) -> None:
        prev_id = self._records[-1].id if self._records else None
        self._records.append(MessageRecord(
            id=_uuid.uuid4(),
            prev_id=prev_id,
            message={"role": "assistant", "content": content},
        ))

    def get_history(self) -> list[MessageRecord]:
        """Return the raw record list (persistence shape).

        This method is intentionally non-overridable — subclasses must not
        shadow it. All LLM-facing message construction goes through get_context().
        """
        # NOTE: Do not override this method in subclasses.
        return list(self._records)

    @property
    def llm(self) -> ILlmPort:
        return self._llm

    @property
    def completion_config(self) -> CompletionConfig:
        return self._completion_config

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """Serialisation key for this strategy (e.g. ``"dummy"``, ``"sliding_window"``, ``"summary"``)."""
        ...

    @abstractmethod
    def get_metadata(self) -> dict:
        """Return a JSON-serialisable dict of strategy state used to restore this strategy via the factory."""
        ...

    @abstractmethod
    async def update_context(self) -> None:
        """Perform any side-effectful update (e.g. LLM summarisation) before context is read.

        Called separately from _get_context so that reads remain free of side effects.
        Default for strategies that need no update: implement as ``pass``.
        """
        ...

    @abstractmethod
    async def get_context(self) -> list[dict[str, str]]:
        """Return the ordered message dicts to send to the LLM, without the system prompt.

        Pure read — must not perform side effects.
        """
        ...
