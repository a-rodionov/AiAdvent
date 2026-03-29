"""Factory for building MessageContextStrategy instances from serialised metadata."""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from server.application.domain.model.context_strategy.dummy_strategy import DummyStrategy
from server.application.domain.model.context_strategy.sliding_window_strategy import SlidingWindowStrategy
from server.application.domain.model.context_strategy.summary_strategy import Summary, SummaryStrategy

if TYPE_CHECKING:
    from server.application.domain.model.completion import CompletionConfig
    from server.application.domain.model.context_strategy.base import MessageContextStrategy, MessageRecord
    from server.application.port.outbound.llm_port import ILlmPort


class MessageContextStrategyFactory:
    @staticmethod
    def build(
        strategy_type: str,
        metadata: dict,
        records: list[MessageRecord],
        llm: ILlmPort,
        completion_config: CompletionConfig,
    ) -> MessageContextStrategy:
        if strategy_type == "dummy":
            return DummyStrategy(records=records, llm=llm, completion_config=completion_config)
        if strategy_type == "summary":
            window_size = int(metadata.get("window_size", 4))
            summary_text: str = metadata.get("summary_text", "")
            raw_anchor_id = metadata.get("summary_anchor_id")
            parsed_anchor: UUID | None = UUID(raw_anchor_id) if raw_anchor_id else None
            summarization_prompt: str = metadata.get("summarization_prompt", "")
            return SummaryStrategy(
                window_size=window_size,
                summarization_prompt=summarization_prompt,
                llm=llm,
                completion_config=completion_config,
                records=records,
                summary=Summary(text=summary_text, anchor_id=parsed_anchor),
            )
        if strategy_type == "sliding_window":
            window_size = int(metadata.get("window_size", 8))
            return SlidingWindowStrategy(
                window_size=window_size,
                records=records,
                llm=llm,
                completion_config=completion_config,
            )
        raise ValueError(f"Unknown strategy type: {strategy_type!r}")
