"""Tests for UsageStats Protocol, UsageStatsAccumulator, and SessionUsageStats.

Spec: ``openspec/specs/usage-stats/spec.md``, ``openspec/specs/session-usage-stats/spec.md``
"""
import pytest

from server.application.domain.model.model_billing import TokensCost
from server.application.domain.model.usage_stats import (
    ModelStats,
    SessionUsageStats,
    TokensUsage,
    UsageStatsAccumulator,
)

# ── 1.1 ModelStats NamedTuple ─────────────────────────────────────────────────

class TestModelStats:
    def test_fields_accessible_by_name(self):
        usage = TokensUsage(prompt_tokens=10, completion_tokens=5)
        cost = TokensCost(prompt_tokens=1.0, completion_tokens=0.5, total_tokens=1.5)
        entry = ModelStats(usage=usage, cost=cost)
        assert entry.usage is usage
        assert entry.cost is cost

    def test_cost_defaults_to_none(self):
        usage = TokensUsage(prompt_tokens=10, completion_tokens=5)
        entry = ModelStats(usage=usage)
        assert entry.cost is None


# ── 1.2 UsageStatsAccumulator construction ────────────────────────────────────

class TestUsageStatsAccumulatorConstruction:
    def test_default_construction_is_falsy(self):
        stats = UsageStatsAccumulator()
        assert not bool(stats)

    def test_construction_with_data_is_truthy(self):
        usage = TokensUsage(prompt_tokens=10, completion_tokens=5)
        data = {"anthropic": {"claude-3": ModelStats(usage=usage)}}
        stats = UsageStatsAccumulator(data=data)
        assert bool(stats)
        assert stats.data["anthropic"]["claude-3"].usage is usage


# ── 1.3 UsageStatsAccumulator.zero() ─────────────────────────────────────────

class TestUsageStatsAccumulatorZero:
    def test_zero_clears_populated_accumulator(self):
        stats = UsageStatsAccumulator()
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10, completion_tokens=5))
        assert bool(stats)
        stats.zero()
        assert not bool(stats)

    def test_zero_on_empty_is_noop(self):
        stats = UsageStatsAccumulator()
        stats.zero()
        assert not bool(stats)


# ── 1.4 UsageStatsAccumulator.add_stats() ────────────────────────────────────

class TestUsageStatsAccumulatorAddStats:
    def test_first_call_creates_entry(self):
        stats = UsageStatsAccumulator()
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10, completion_tokens=5))
        assert stats.data["openai"]["gpt-4"].usage.prompt_tokens == 10
        assert stats.data["openai"]["gpt-4"].usage.completion_tokens == 5

    def test_second_call_accumulates_token_counts(self):
        stats = UsageStatsAccumulator()
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10, completion_tokens=5))
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10, completion_tokens=3))
        assert stats.data["openai"]["gpt-4"].usage.prompt_tokens == 20
        assert stats.data["openai"]["gpt-4"].usage.completion_tokens == 8

    def test_cost_accumulates_when_both_calls_provide_cost(self):
        stats = UsageStatsAccumulator()
        cost = TokensCost(prompt_tokens=1.5, completion_tokens=0.5, total_tokens=2.0)
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10), cost=cost)
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10), cost=cost)
        assert stats.data["openai"]["gpt-4"].cost.prompt_tokens == pytest.approx(3.0)
        assert stats.data["openai"]["gpt-4"].cost.total_tokens == pytest.approx(4.0)

    def test_cost_remains_none_when_both_calls_pass_no_cost(self):
        stats = UsageStatsAccumulator()
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10))
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=10))
        assert stats.data["openai"]["gpt-4"].cost is None

    def test_different_pairs_tracked_independently(self):
        stats = UsageStatsAccumulator()
        stats.add_stats("anthropic", "claude-3", TokensUsage(prompt_tokens=100))
        stats.add_stats("openai", "gpt-4", TokensUsage(prompt_tokens=200))
        assert stats.data["anthropic"]["claude-3"].usage.prompt_tokens == 100
        assert stats.data["openai"]["gpt-4"].usage.prompt_tokens == 200


# ── 1.5 UsageStatsAccumulator.__bool__ and .data ─────────────────────────────

class TestUsageStatsAccumulatorBoolAndData:
    def test_empty_is_falsy(self):
        assert not bool(UsageStatsAccumulator())

    def test_nonempty_is_truthy(self):
        stats = UsageStatsAccumulator()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=1))
        assert bool(stats)

    def test_data_reflects_current_state(self):
        stats = UsageStatsAccumulator()
        usage = TokensUsage(prompt_tokens=5, completion_tokens=3)
        stats.add_stats("p", "m", usage)
        assert stats.data["p"]["m"].usage.prompt_tokens == 5

    def test_data_is_live_reference(self):
        stats = UsageStatsAccumulator()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=1))
        d = stats.data
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=1))
        assert d["p"]["m"].usage.prompt_tokens == 2


# ── SessionUsageStats ─────────────────────────────────────────────────────────

class TestSessionUsageStats:
    def test_default_construction_both_empty(self):
        stats = SessionUsageStats()
        assert stats.current_invocation_data == {}
        assert stats.lifecycle_total_data == {}

    def test_construction_with_data_populates_lifecycle(self):
        usage = TokensUsage(prompt_tokens=100, completion_tokens=50)
        data = {"anthropic": {"claude-3": ModelStats(usage=usage)}}
        stats = SessionUsageStats(data=data)
        assert stats.lifecycle_total_data["anthropic"]["claude-3"].usage.prompt_tokens == 100
        assert stats.current_invocation_data == {}

    def test_add_stats_updates_both_accumulators(self):
        stats = SessionUsageStats()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=10, completion_tokens=5))
        assert stats.current_invocation_data["p"]["m"].usage.prompt_tokens == 10
        assert stats.lifecycle_total_data["p"]["m"].usage.prompt_tokens == 10

    def test_multiple_add_stats_accumulate_in_both(self):
        stats = SessionUsageStats()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=10, completion_tokens=5))
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=10, completion_tokens=5))
        assert stats.current_invocation_data["p"]["m"].usage.prompt_tokens == 20
        assert stats.lifecycle_total_data["p"]["m"].usage.prompt_tokens == 20

    def test_begin_invocation_clears_current_preserves_lifecycle(self):
        stats = SessionUsageStats()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=10, completion_tokens=5))
        stats.begin_invocation()
        assert stats.current_invocation_data == {}
        assert stats.lifecycle_total_data["p"]["m"].usage.prompt_tokens == 10

    def test_begin_invocation_on_fresh_is_noop(self):
        stats = SessionUsageStats()
        stats.begin_invocation()
        assert stats.current_invocation_data == {}
        assert stats.lifecycle_total_data == {}

    def test_current_invocation_data_empty_after_begin_invocation(self):
        stats = SessionUsageStats()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=5))
        stats.begin_invocation()
        assert stats.current_invocation_data == {}

    def test_lifecycle_accumulates_across_invocations(self):
        stats = SessionUsageStats()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=10))
        stats.begin_invocation()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=10))
        stats.begin_invocation()
        assert stats.lifecycle_total_data["p"]["m"].usage.prompt_tokens == 20
        assert stats.current_invocation_data == {}

    def test_satisfies_usage_stats_protocol(self):
        """SessionUsageStats satisfies the UsageStats Protocol (has add_stats method)."""
        from server.application.domain.model.usage_stats import UsageStats
        # Both have the same add_stats signature — structural subtyping check
        stats = SessionUsageStats()
        # This should work without error (duck typing / structural subtyping)
        def _accept_usage_stats(s: UsageStats) -> None:
            s.add_stats("p", "m", TokensUsage(prompt_tokens=1))
        _accept_usage_stats(stats)
        assert stats.lifecycle_total_data["p"]["m"].usage.prompt_tokens == 1
