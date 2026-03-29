"""LlmStatsDecorator — domain-layer decorator for transparent stats accumulation.

Wraps an ILlmPort, intercepts CompletionDoneEvent to accumulate token usage
and optional cost into a SessionUsageStats instance. Satisfies ILlmPort via
structural subtyping (Protocol).

Spec: ``openspec/specs/llm-stats-decorator/spec.md``
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.model_billing import ModelBilling, TokensCost
from server.application.domain.model.usage_stats import SessionUsageStats

if TYPE_CHECKING:
    from server.application.port.outbound.llm_port import CompletionEvent, ILlmPort


class LlmStatsDecorator:
    """Decorator wrapping an ILlmPort that intercepts CompletionDoneEvent for stats.

    TextChunkEvent instances are forwarded unchanged. On CompletionDoneEvent, token
    usage is extracted and accumulated into SessionUsageStats. If a ModelBilling is
    provided, cost is also estimated and accumulated. The CompletionDoneEvent is then
    yielded to the caller.

    KeyError from ModelBilling.estimate (unknown provider/model) is caught silently
    and cost falls back to None.
    """

    def __init__(
        self,
        llm: ILlmPort,
        usage_stats: SessionUsageStats,
        billing: ModelBilling | None = None,
    ) -> None:
        self._llm = llm
        self._usage_stats = usage_stats
        self._billing = billing

    async def acompletion(
        self,
        full_messages: list,
        completion_config: CompletionConfig,
        is_stream_prefered: bool,
    ) -> AsyncGenerator[CompletionEvent, None]:
        from server.application.port.outbound.llm_port import CompletionDoneEvent, TextChunkEvent

        async for event in self._llm.acompletion(full_messages, completion_config, is_stream_prefered):
            if isinstance(event, TextChunkEvent):
                yield event
            elif isinstance(event, CompletionDoneEvent):
                cost: TokensCost | None = None
                if self._billing is not None:
                    try:
                        cost = self._billing.estimate(
                            base_input_tokens=event.tokens_usage.prompt_tokens,
                            output_tokens=event.tokens_usage.completion_tokens,
                        )
                    except KeyError:
                        cost = None
                self._usage_stats.add_stats(
                    event.provider,
                    event.model,
                    usage=event.tokens_usage,
                    cost=cost,
                )
                yield event
