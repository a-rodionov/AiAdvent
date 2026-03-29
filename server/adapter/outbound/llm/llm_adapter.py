import time
from collections.abc import AsyncGenerator

from any_llm import AnyLLM

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.session import StopReason
from server.application.domain.model.usage_stats import TokensUsage
from server.application.port.outbound.llm_port import CompletionDoneEvent, CompletionEvent, ILlmPort, TextChunkEvent


def _build_kwargs(completion_config: CompletionConfig, messages: list, is_stream_prefered: bool) -> dict:
    """Build any-llm amessages kwargs from completion config."""
    kwargs: dict = {
        "model": completion_config.model,
        "messages": messages,
        "max_tokens": completion_config.max_tokens,
    }
    if completion_config.temperature is not None:
        kwargs["temperature"] = completion_config.temperature
    if completion_config.top_k is not None:
        kwargs["top_k"] = completion_config.top_k
    if completion_config.temperature is None and completion_config.top_p is not None:
        kwargs["top_p"] = completion_config.top_p
    if completion_config.stop_sequences is not None:
        kwargs["stop"] = completion_config.stop_sequences
    if completion_config.output_config is not None:
        kwargs["response_format"] = completion_config.output_config
    if is_stream_prefered and completion_config.output_config is None:
        kwargs["stream"] = True
    return kwargs


class LlmAdapter(ILlmPort):
    def __init__(self, provider: str):
        self._llm = AnyLLM.create(provider)

    async def acompletion(
        self,
        full_messages: list,
        completion_config: CompletionConfig,
        is_stream_prefered: bool,
    ) -> AsyncGenerator[CompletionEvent, None]:
        if completion_config.provider != self._llm.PROVIDER_NAME:
            raise ValueError(
                f"Provider mismatch: completion_config.provider={completion_config.provider!r} "
                f"does not match llm.PROVIDER_NAME={self._llm.PROVIDER_NAME!r}"
            )
        start_time = time.monotonic()

        kwargs = _build_kwargs(completion_config, full_messages, is_stream_prefered)

        prompt_tokens = 0
        completion_tokens = 0
        stop_reason = StopReason.STOP
        if kwargs.get("stream", False) is False:
            response = await self._llm.acompletion(**kwargs)
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            choice = response.choices[0]
            stop_reason = choice.finish_reason
            yield TextChunkEvent(text=choice.message.content or "")
        else:
            stream = await self._llm.acompletion(**kwargs)
            async for chunk in stream:
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason:
                    stop_reason = choice.finish_reason
                    # По какой-то причине всегда возвращается StopReason.STOP
                    if (StopReason(stop_reason) == StopReason.STOP and
                            completion_config.max_tokens == completion_tokens):
                        stop_reason = StopReason.LENGTH
                if choice.delta.content:
                    yield TextChunkEvent(text=choice.delta.content)
        elapsed_s = (time.monotonic() - start_time)
        done_event = CompletionDoneEvent(
            provider=self._llm.PROVIDER_NAME,
            model=completion_config.model,
            tokens_usage=TokensUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
            stop_reason=StopReason(stop_reason) if stop_reason else StopReason.STOP,
            elapsed_s=int(elapsed_s),
        )
        yield done_event
