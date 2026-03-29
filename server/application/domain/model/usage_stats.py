"""UsageStats Protocol, concrete accumulator, SessionUsageStats, and ModelStats entry type.

Spec: ``openspec/specs/usage-stats/spec.md``, ``openspec/specs/session-usage-stats/spec.md``
"""
from typing import NamedTuple, Protocol

from pydantic import BaseModel, Field

from server.application.domain.model.model_billing import TokensCost


class TokensUsage(BaseModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)


class ModelStats(NamedTuple):
    usage: TokensUsage
    cost: TokensCost | None = None


class UsageStats(Protocol):
    """Protocol for token usage accumulation.

    Classes satisfying this protocol can be used interchangeably wherever
    usage stats accumulation is needed. Both `UsageStatsAccumulator` and
    `SessionUsageStats` satisfy this protocol structurally.
    """

    def add_stats(
        self,
        provider: str,
        model: str,
        usage: TokensUsage,
        cost: TokensCost | None = None,
    ) -> None: ...


class UsageStatsAccumulator:
    """Mutable per-(provider, model) token and cost accumulator."""

    def __init__(self, data: dict[str, dict[str, ModelStats]] | None = None) -> None:
        self._data: dict[str, dict[str, ModelStats]] = data if data is not None else {}

    def __bool__(self) -> bool:
        return bool(self._data)

    @property
    def data(self) -> dict[str, dict[str, ModelStats]]:
        return self._data

    def zero(self) -> None:
        """Clear all accumulated entries."""
        self._data.clear()

    def add_stats(
        self,
        provider: str,
        model: str,
        usage: TokensUsage,
        cost: TokensCost | None = None,
    ) -> None:
        """Accumulate *usage* and optional *cost* for the given *(provider, model)* pair."""
        provider_data = self._data.setdefault(provider, {})
        if model not in provider_data:
            provider_data[model] = ModelStats(usage=usage, cost=cost)
            return

        existing = provider_data[model]
        new_usage = TokensUsage(
            prompt_tokens=existing.usage.prompt_tokens + usage.prompt_tokens,
            completion_tokens=existing.usage.completion_tokens + usage.completion_tokens,
        )

        # Cost accumulation: None+None→None; otherwise sum treating None as zero
        if existing.cost is None and cost is None:
            new_cost = None
        else:
            ex = existing.cost
            ev = cost
            new_cost = TokensCost(
                prompt_tokens=(ex.prompt_tokens if ex else 0.0) + (ev.prompt_tokens if ev else 0.0),
                completion_tokens=(ex.completion_tokens if ex else 0.0) + (ev.completion_tokens if ev else 0.0),
                total_tokens=(ex.total_tokens if ex else 0.0) + (ev.total_tokens if ev else 0.0),
            )

        provider_data[model] = ModelStats(usage=new_usage, cost=new_cost)


class SessionUsageStats:
    """Two-level usage stats accumulator owned by Session.

    Maintains a per-invocation accumulator (`_current_invocation`) and a
    cumulative lifecycle accumulator (`_lifecycle_total`). Both are updated on
    every `add_stats` call. `begin_invocation` resets only the per-request one.

    Satisfies the `UsageStats` Protocol structurally via `add_stats`.

    Spec: ``openspec/specs/session-usage-stats/spec.md``
    """

    def __init__(self, data: dict[str, dict[str, ModelStats]] | None = None) -> None:
        self._lifecycle_total = UsageStatsAccumulator(data=data)
        self._current_invocation = UsageStatsAccumulator()

    def add_stats(
        self,
        provider: str,
        model: str,
        usage: TokensUsage,
        cost: TokensCost | None = None,
    ) -> None:
        """Delegate to both current-invocation and lifecycle accumulators."""
        self._current_invocation.add_stats(provider, model, usage, cost)
        self._lifecycle_total.add_stats(provider, model, usage, cost)

    def begin_invocation(self) -> None:
        """Reset per-request statistics; lifecycle total is preserved."""
        self._current_invocation.zero()

    @property
    def current_invocation_data(self) -> dict[str, dict[str, ModelStats]]:
        return self._current_invocation.data

    @property
    def lifecycle_total_data(self) -> dict[str, dict[str, ModelStats]]:
        return self._lifecycle_total.data

    def __bool__(self) -> bool:
        return bool(self._lifecycle_total)
