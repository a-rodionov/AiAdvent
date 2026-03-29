"""Dummy (no-op) message context strategy — retains all records unchanged."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.application.domain.model.context_strategy.base import MessageContextStrategy

if TYPE_CHECKING:
    from server.application.domain.model.completion import CompletionConfig
    from server.application.domain.model.context_strategy.base import MessageRecord
    from server.application.port.outbound.llm_port import ILlmPort


class DummyStrategy(MessageContextStrategy):
    def __init__(self, llm: ILlmPort, completion_config: CompletionConfig, records: list[MessageRecord] | None = None):
        super().__init__(llm, completion_config, records)

    @property
    def strategy_type(self) -> str:
        return "dummy"

    async def update_context(self) -> None:
        pass

    async def get_context(self) -> list[dict[str, str]]:
        return [r.message for r in self._records]

    def get_metadata(self) -> dict:
        return {}
