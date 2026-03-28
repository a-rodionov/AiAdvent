from datetime import datetime
from typing import AsyncGenerator, Literal, Optional
from pydantic import BaseModel, Field
from completion_config import CompletionConfig
from llm_adapter import LlmAdapter, TextChunkEvent, CompletionDoneEvent, StopReason, TokensUsage
from model_pricing import ModelPricing


class TokensCost(BaseModel):
    prompt_tokens: float = Field(default=0.0, ge=0)
    completion_tokens: float = Field(default=0.0, ge=0)
    total_tokens: float = Field(default=0.0, ge=0)


class SessionEvent(BaseModel):
    pass


class SessionTextChunkEvent(SessionEvent):
    type: Literal["session_text_chunk"] = "session_text_chunk"
    text: str


class SessionCompletionDoneEvent(SessionEvent):
    type: Literal["session_completion_done"] = "session_completion_done"
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tokens_usage: TokensUsage
    stop_reason: StopReason
    elapsed_s: int = Field(ge=0)
    tokens_cost: Optional[TokensCost] = None


class SessionStatistics(BaseModel):
    tokens_usage: TokensUsage
    tokens_cost: Optional[TokensCost] = None


class SessionDto(BaseModel):
    id: str = Field(min_length=1)
    created_at: datetime
    completion_config: CompletionConfig
    statistics: Optional[dict[str, SessionStatistics]] = None
    messages: list = Field(default_factory=list)


class Session:
    def __init__(self, llm: LlmAdapter,  model_pricing: ModelPricing, id: str, created_at: datetime,
                 completion_config: CompletionConfig, statistics: dict[str, SessionStatistics], messages: list):
        self._llm = llm
        self._model_pricing = model_pricing
        self._id = id
        self._created_at = created_at
        self._completion_config = completion_config
        self._statistics = statistics
        self._messages = messages

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
    def statistics(self) -> Optional[dict]:
        return self._statistics

    @property
    def messages(self) -> list:
        return self._messages

    @classmethod
    def create(cls, llm: LlmAdapter, id: str, model_pricing: ModelPricing, completion_config: CompletionConfig) -> "Session":
        return cls(llm, model_pricing, id, datetime.now(), completion_config, None, [])

    @classmethod
    def from_dto(cls, llm: LlmAdapter, model_pricing: ModelPricing, dto: SessionDto) -> "Session":
        return cls(llm, model_pricing, dto.id, dto.created_at, dto.completion_config, dto.statistics, dto.messages)

    def to_dto(self) -> SessionDto:
        return SessionDto(
            id=self._id,
            created_at=self._created_at,
            completion_config=self._completion_config,
            statistics=self._statistics,
            messages=self._messages,
        )
        
    def _handle_completion_done_event(self, event: SessionCompletionDoneEvent) -> None:
        if self._statistics is None:
            self._statistics = {}

        key = f"{event.provider},{event.model}"

        if key in self._statistics:
            existing = self._statistics[key]
            new_usage = TokensUsage(
                prompt_tokens=existing.tokens_usage.prompt_tokens + event.tokens_usage.prompt_tokens,
                completion_tokens=existing.tokens_usage.completion_tokens + event.tokens_usage.completion_tokens,
            )
            if existing.tokens_cost is not None or event.tokens_cost is not None:
                ex = existing.tokens_cost
                ev = event.tokens_cost
                new_cost = TokensCost(
                    prompt_tokens=(ex.prompt_tokens if ex else 0.0) + (ev.prompt_tokens if ev else 0.0),
                    completion_tokens=(ex.completion_tokens if ex else 0.0) + (ev.completion_tokens if ev else 0.0),
                    total_tokens=(ex.total_tokens if ex else 0.0) + (ev.total_tokens if ev else 0.0),
                )
            else:
                new_cost = None
            self._statistics[key] = SessionStatistics(tokens_usage=new_usage, tokens_cost=new_cost)
        else:
            self._statistics[key] = SessionStatistics(
                tokens_usage=event.tokens_usage,
                tokens_cost=event.tokens_cost,
            )

    async def acompletion(self, prompt: str, is_stream_prefered: bool) -> AsyncGenerator[SessionEvent, None]:
        self._messages.append({"role": "user", "content": prompt})
        full_messages = []
        if self._completion_config.system_prompt:
            full_messages.append({"role": "system", "content": self._completion_config.system_prompt})
        full_messages.extend(self._messages)

        assistant_text = ""
        async for event in self._llm.acompletion(full_messages, self._completion_config, is_stream_prefered):
            if isinstance(event, TextChunkEvent):
                assistant_text += event.text
                yield SessionTextChunkEvent(text=event.text)
            elif isinstance(event, CompletionDoneEvent):
                tokens_cost = self._model_pricing.estimate(
                    provider=event.provider,
                    model=event.model,
                    base_input_tokens=event.tokens_usage.prompt_tokens,
                    output_tokens=event.tokens_usage.completion_tokens,
                )
                done_event = SessionCompletionDoneEvent(
                    provider=event.provider,
                    model=event.model,
                    tokens_usage=TokensUsage(
                        prompt_tokens=event.tokens_usage.prompt_tokens,
                        completion_tokens=event.tokens_usage.completion_tokens,
                    ),
                    stop_reason=event.stop_reason,
                    elapsed_s=event.elapsed_s,
                    tokens_cost=TokensCost(
                        prompt_tokens=tokens_cost.base_input_tokens_cost,
                        completion_tokens=tokens_cost.output_tokens_cost,
                        total_tokens=tokens_cost.total_cost,
                    ) if tokens_cost is not None else None
                )
                self._handle_completion_done_event(done_event)
                yield done_event

        self._messages.append({"role": "assistant", "content": assistant_text})
