"""LlmPortFactoryAdapter — creates and caches LlmAdapter instances per session and provider.

Spec: ``openspec/specs/llm-port-factory/spec.md``
"""
from server.adapter.outbound.llm.llm_adapter import LlmAdapter
from server.application.domain.model.completion import CompletionConfig
from server.application.port.outbound.llm_port import ILlmPort


class LlmPortFactoryAdapter:
    """Creates LlmAdapter instances with a nested cache keyed by (session_id, provider)."""

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, LlmAdapter]] = {}

    def create(self, session_id: str, completion_config: CompletionConfig) -> ILlmPort:
        """Return a cached LlmAdapter for (session_id, provider), creating one if needed."""
        provider = completion_config.provider
        session_cache = self._cache.setdefault(session_id, {})
        if provider not in session_cache:
            session_cache[provider] = LlmAdapter(provider)
        return session_cache[provider]
