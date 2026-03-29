"""Sliding-window message context strategy — keeps only the last N records."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.application.domain.model.context_strategy.base import MessageContextStrategy

if TYPE_CHECKING:
    from server.application.domain.model.completion import CompletionConfig
    from server.application.domain.model.context_strategy.base import MessageRecord
    from server.application.port.outbound.llm_port import ILlmPort


class SlidingWindowStrategy(MessageContextStrategy):
    def __init__(
        self,
        window_size: int,
        llm: ILlmPort,
        completion_config: CompletionConfig,
        records: list[MessageRecord] | None = None,
    ):
        if window_size < 1:
            raise ValueError(f"SlidingWindowStrategy. window_size must be >= 1, got {window_size}")
        self._window_size = window_size
        super().__init__(llm, completion_config, records)

    @property
    def strategy_type(self) -> str:
        return "sliding_window"

    async def update_context(self) -> None:
        pass

    async def get_context(self) -> list[dict[str, str]]:
        return [r.message for r in self._records[-self._window_size:]]

    def get_metadata(self) -> dict:
        return {"window_size": self._window_size}
