"""ILlmPortFactory port — factory for creating ILlmPort instances.

Spec: ``openspec/specs/llm-port-factory/spec.md``
"""
from typing import Protocol

from server.application.domain.model.completion import CompletionConfig
from server.application.port.outbound.llm_port import ILlmPort


class ILlmPortFactory(Protocol):
    """Factory port for creating ILlmPort instances per session and provider."""

    def create(self, session_id: str, completion_config: CompletionConfig) -> ILlmPort: ...
