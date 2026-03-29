"""Session aggregate root for LLM conversation management.

:class:`Session` is the central domain object that orchestrates one conversation
with an LLM. It owns the message-context strategy, accumulates token-usage
statistics via LlmStatsDecorator, and exposes a streaming completion API.

Spec: ``openspec/specs/session/spec.md``
"""
from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.context_strategy import (
    MessageContextStrategy,
    MessageContextStrategyFactory,
    MessageRecord,
)
from server.application.domain.model.llm_stats_decorator import LlmStatsDecorator
from server.application.domain.model.model_billing import ModelBilling
from server.application.domain.model.usage_stats import ModelStats, SessionUsageStats

if TYPE_CHECKING:
    from server.application.port.outbound.llm_port import ILlmPort


# ── Stop reason ───────────────────────────────────────────────────────────────

class StopReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"


# ── Session events ────────────────────────────────────────────────────────────

class SessionEvent(BaseModel):
    pass


class SessionTextChunkEvent(SessionEvent):
    type: Literal["session_text_chunk"] = "session_text_chunk"
    text: str


class SessionCompletionDoneEvent(SessionEvent):
    type: Literal["session_completion_done"] = "session_completion_done"
    stop_reason: StopReason
    elapsed_s: int = Field(ge=0)
    statistics: dict[str, dict[str, ModelStats]] | None = None


# ── Session state (used for persistence) ─────────────────────────────────────

class SessionState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(min_length=1)
    created_at: datetime
    completion_config: CompletionConfig
    statistics: dict[str, dict[str, ModelStats]] | None = None
    strategy_type: str
    strategy_metadata: dict = Field(default_factory=dict)
    strategy_completion_config: CompletionConfig
    strategy_records: list[MessageRecord] = Field(default_factory=list)


# ── Session aggregate root ────────────────────────────────────────────────────

class Session:
    def __init__(
        self,
        llm: ILlmPort,
        id: str,
        created_at: datetime,
        completion_config: CompletionConfig,
        billing: ModelBilling | None,
        usage_stats: SessionUsageStats,
        message_context_strategy: MessageContextStrategy,
    ):
        self._id = id
        self._created_at = created_at
        self._completion_config = completion_config
        self._usage_stats = usage_stats
        self._llm_stats = LlmStatsDecorator(llm=llm, usage_stats=self._usage_stats, billing=billing)
        self._message_context_strategy = message_context_strategy

    @property
    def id(self) -> str:
        return self._id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def completion_config(self) -> CompletionConfig:
        return self._completion_config

    @property
    def statistics(self) -> SessionUsageStats:
        return self._usage_stats

    @property
    def message_context_strategy(self) -> MessageContextStrategy:
        return self._message_context_strategy

    @property
    def messages(self) -> list:
        """Return raw MessageRecord list (persistence shape) — not for LLM calls.

        This exposes the full unfiltered record history. LLM-facing context
        (with system prompt and strategy filtering) is produced by get_context().
        """
        return self._message_context_strategy.get_history()

    async def set_message_context_strategy(self, strategy: MessageContextStrategy) -> None:
        """Replace the active strategy; transplants existing records into the new strategy via the factory."""
        existing_records = self._message_context_strategy.get_history()
        self._message_context_strategy = MessageContextStrategyFactory.build(
            strategy.strategy_type,
            strategy.get_metadata(),
            existing_records,
            strategy.llm,
            strategy.completion_config,
        )

    @classmethod
    async def create(
        cls,
        llm: ILlmPort,
        id: str,
        completion_config: CompletionConfig,
        billing: ModelBilling | None,
        strategy_type: str,
        strategy_metadata: dict,
        strategy_llm: ILlmPort,
        strategy_completion_config: CompletionConfig,
        strategy_billing: ModelBilling | None,
    ) -> Session:
        usage_stats = SessionUsageStats()
        strategy_llm_stats = LlmStatsDecorator(
            llm=strategy_llm, usage_stats=usage_stats, billing=strategy_billing
        )
        strategy = MessageContextStrategyFactory.build(
            strategy_type, strategy_metadata, [], strategy_llm_stats, strategy_completion_config
        )
        return cls(
            llm=llm,
            id=id,
            created_at=datetime.now(),
            completion_config=completion_config,
            billing=billing,
            usage_stats=usage_stats,
            message_context_strategy=strategy,
        )

    async def acompletion(self, prompt: str, is_stream_prefered: bool) -> AsyncGenerator[SessionEvent, None]:
        """Yield zero or more :class:`SessionTextChunkEvent`s then one final :class:`SessionCompletionDoneEvent`."""
        from server.application.port.outbound.llm_port import CompletionDoneEvent, TextChunkEvent

        self._usage_stats.begin_invocation()
        assistant_text = ""
        start_time = time.monotonic()
        stop_reason: StopReason | None = None

        await self._message_context_strategy.add_user_query(prompt)
        context = await self._message_context_strategy.get_context()

        async for event in self._llm_stats.acompletion(context, self._completion_config, is_stream_prefered):
            if isinstance(event, TextChunkEvent):
                assistant_text += event.text
                yield SessionTextChunkEvent(text=event.text)
            elif isinstance(event, CompletionDoneEvent):
                stop_reason = event.stop_reason

        await self._message_context_strategy.add_model_response(assistant_text)
        await self._message_context_strategy.update_context()

        elapsed_s = (time.monotonic() - start_time)
        done_event = SessionCompletionDoneEvent(
            stop_reason=stop_reason or StopReason.STOP,
            elapsed_s=int(elapsed_s),
            statistics=self._usage_stats.current_invocation_data or None,
        )
        yield done_event
