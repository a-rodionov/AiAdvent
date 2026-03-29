"""Summary-based message context strategy — condenses old history into a rolling summary."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple

from server.application.domain.model.context_strategy.base import MessageContextStrategy

if TYPE_CHECKING:
    from uuid import UUID

    from server.application.domain.model.completion import CompletionConfig
    from server.application.domain.model.context_strategy.base import MessageRecord
    from server.application.port.outbound.llm_port import ILlmPort

logger = logging.getLogger(__name__)


class Summary(NamedTuple):
    text: str
    anchor_id: UUID | None


class SummaryStrategy(MessageContextStrategy):
    def __init__(
        self,
        window_size: int,
        summarization_prompt: str,
        llm: ILlmPort,
        completion_config: CompletionConfig,
        records: list[MessageRecord] | None = None,
        summary: Summary | None = None,
    ):
        if window_size < 1:
            raise ValueError(f"SummaryStrategy. window_size must be >= 1, got {window_size}")
        if llm is None:
            raise ValueError("SummaryStrategy. LlmPort object is None")
        if summarization_prompt is None or summarization_prompt == "":
            raise ValueError("SummaryStrategy. summarization_prompt must be not empty string")
        self._window_size = window_size
        self._summarization_prompt = summarization_prompt
        self._summary: Summary = summary if summary is not None else Summary("", None)
        super().__init__(llm, completion_config, records)

    @property
    def strategy_type(self) -> str:
        return "summary"

    async def update_context(self) -> None:
        """Trigger LLM summarisation if records since anchor >= window_size."""
        if self._summary.anchor_id is None:
            records_after_anchor = self._records
        else:
            anchor_index = next(
                (i for i, r in enumerate(self._records) if r.id == self._summary.anchor_id),
                None,
            )
            records_after_anchor = self._records[anchor_index + 1:] if anchor_index is not None else self._records

        count_since_anchor = len(records_after_anchor)
        logger.info(
            "SummaryStrategy: records since anchor: %d. Window size: %d",
            count_since_anchor,
            self._window_size,
        )

        if count_since_anchor >= self._window_size:
            input_for_summarization: list[dict[str, str]] = []
            if self._summary.text:
                input_for_summarization.append({"role": "user", "content": self._summary.text})
            input_for_summarization.extend(r.message for r in records_after_anchor)

            llm_input: list[dict[str, str]] = []
            if self._completion_config.system_prompt:
                llm_input.append({"role": "system", "content": self._completion_config.system_prompt})
                logger.info("SummaryStrategy system prompt: %s", self._completion_config.system_prompt)
            llm_input.append({"role": "user", "content": self._summarization_prompt % str(input_for_summarization)})
            logger.info("SummaryStrategy llm_input: %s", llm_input)

            from server.application.port.outbound.llm_port import CompletionDoneEvent, TextChunkEvent

            assistant_text = ""
            async for event in self._llm.acompletion(llm_input, self._completion_config, False):
                if isinstance(event, TextChunkEvent):
                    assistant_text += event.text
                elif isinstance(event, CompletionDoneEvent):
                    pass  # Stats accumulated transparently by LlmStatsDecorator

            self._summary = Summary(text=assistant_text, anchor_id=self._records[-1].id)
            logger.info("SummaryStrategy updated summary: %s (anchor: %s)", self._summary.text, self._summary.anchor_id)

    async def get_context(self) -> list[dict[str, str]]:
        """Return LLM-facing message dicts using the current summary (no side effects)."""
        if self._summary.anchor_id is None:
            return [r.message for r in self._records]

        anchor_index = next(
            (i for i, r in enumerate(self._records) if r.id == self._summary.anchor_id),
            None,
        )
        records_after_anchor = self._records[anchor_index + 1:] if anchor_index is not None else self._records

        if self._summary.text:
            return [{"role": "user", "content": self._summary.text}] + [r.message for r in records_after_anchor]
        return [r.message for r in records_after_anchor]

    def get_metadata(self) -> dict:
        return {
            "window_size": self._window_size,
            "summary_text": self._summary.text,
            "summary_anchor_id": str(self._summary.anchor_id) if self._summary.anchor_id is not None else None,
            "summarization_prompt": self._summarization_prompt,
        }
