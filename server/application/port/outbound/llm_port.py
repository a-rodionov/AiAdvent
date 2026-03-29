from collections.abc import AsyncGenerator
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.session import StopReason
from server.application.domain.model.usage_stats import TokensUsage

# ── Events emitted by the LLM port ───────────────────────────────────────────

class CompletionEvent(BaseModel):
    pass


class TextChunkEvent(CompletionEvent):
    """A partial text delta emitted during streaming.

    Yielded zero or more times before the terminal `CompletionDoneEvent`.
    Each instance carries one incremental fragment of the assistant reply.

    Attributes:
        text: The incremental string fragment produced by the LLM in this chunk.
    """

    type: Literal["llm_adapter_text_chunk"] = "llm_adapter_text_chunk"
    text: str


class CompletionDoneEvent(CompletionEvent):
    """The mandatory terminal event that closes every `acompletion` stream.

    Always the last event yielded by a conforming adapter, even when
    `is_stream_prefered` is `False`. Carries final request metadata.

    Attributes:
        provider: The provider identifier used for this completion (e.g. ``"anthropic"``).
        model: The model identifier as reported by the provider.
        tokens_usage: Input and output token counts for the request.
        stop_reason: Why the model stopped generating (default: ``StopReason.STOP``).
        elapsed_s: Wall-clock seconds from request dispatch to response completion.
    """

    type: Literal["llm_adapter_completion_done"] = "llm_adapter_completion_done"
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tokens_usage: TokensUsage
    stop_reason: StopReason = Field(default=StopReason.STOP)
    elapsed_s: int = Field(default=0, ge=0)


# ── Port ─────────────────────────────────────────────────────────────────────

class ILlmPort(Protocol):
    """Hexagonal-architecture port defining the contract for LLM completion providers.

    The domain layer depends only on this protocol — never on concrete SDK types
    (e.g. Anthropic, OpenAI). Implementors satisfy the protocol through structural
    subtyping — they do not need to inherit from `ILlmPort`.
    """

    def acompletion(
        self,
        full_messages: list,
        completion_config: CompletionConfig,
        is_stream_prefered: bool,
    ) -> AsyncGenerator[CompletionEvent, None]:
        """Stream a chat completion as an async generator of `CompletionEvent` items.

        Event ordering contract (normative):
            1. Zero or more :class:`TextChunkEvent` items — partial text deltas.
            2. Exactly one :class:`CompletionDoneEvent` — always the terminal event.

        No events SHALL be emitted after `CompletionDoneEvent`. This contract holds
        regardless of the value of `is_stream_prefered`.

        Args:
            full_messages: Conversation history in the provider-native dict format
                (e.g. ``[{"role": "user", "content": "Hello"}]``). The adapter is
                responsible for any provider-specific message transformation.
            completion_config: Provider, model, and sampling settings that drive
                the completion request (temperature, max tokens, output schema, …).
            is_stream_prefered: Hint to the adapter to use the streaming API if the
                provider supports it. Adapters MAY ignore this hint; the event
                ordering contract is guaranteed in both streaming and non-streaming
                paths.

        Yields:
            A sequence of :class:`CompletionEvent` subclasses following the ordering
            contract above.
        """
        ...
