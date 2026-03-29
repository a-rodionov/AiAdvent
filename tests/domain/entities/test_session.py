"""Unit tests for server.domain.entities.session.

Tests cover the Session aggregate root and SessionUsageStats integration.
The LLM port is mocked via an async generator — consistent with the
pattern used in tests/use_cases/conftest.py.
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.context_strategy import DummyStrategy, SlidingWindowStrategy
from server.application.domain.model.session import (
    Session,
    SessionCompletionDoneEvent,
    SessionState,
    SessionTextChunkEvent,
    StopReason,
)
from server.application.domain.model.usage_stats import SessionUsageStats, TokensUsage
from server.application.port.outbound.llm_port import CompletionDoneEvent, ILlmPort, TextChunkEvent

# ── Helpers ───────────────────────────────────────────────────────────────────

def _config():
    return CompletionConfig(provider="test_provider", model="test_model", max_tokens=100)


def _make_llm(text_chunks: list[str] | None = None, provider="test_provider", model="test_model"):
    llm = MagicMock(spec=ILlmPort)

    async def _acompletion(full_messages, completion_config, is_stream_prefered):
        for chunk in (text_chunks or ["Hello!"]):
            yield TextChunkEvent(text=chunk)
        yield CompletionDoneEvent(
            provider=provider,
            model=model,
            tokens_usage=TokensUsage(prompt_tokens=10, completion_tokens=5),
            stop_reason=StopReason.STOP,
            elapsed_s=1,
        )

    llm.acompletion = _acompletion
    return llm


async def _make_session(llm=None, cfg=None, strategy_type="dummy"):
    llm = llm or _make_llm()
    cfg = cfg or _config()
    return await Session.create(
        llm=llm,
        id="sess-1",
        completion_config=cfg,
        billing=None,
        strategy_type=strategy_type,
        strategy_metadata={},
        strategy_llm=llm,
        strategy_completion_config=cfg,
        strategy_billing=None,
    )


# ── SessionUsageStats integration ─────────────────────────────────────────────

class TestSessionUsageStats:
    def test_creates_new_entry_for_unknown_key(self):
        stats = SessionUsageStats()
        stats.add_stats("test_provider", "test_model", TokensUsage(prompt_tokens=10, completion_tokens=5))
        assert stats.lifecycle_total_data["test_provider"]["test_model"].usage.prompt_tokens == 10
        assert stats.lifecycle_total_data["test_provider"]["test_model"].usage.completion_tokens == 5

    def test_accumulates_tokens_for_existing_key(self):
        stats = SessionUsageStats()
        stats.add_stats("test_provider", "test_model", TokensUsage(prompt_tokens=10, completion_tokens=5))
        stats.add_stats("test_provider", "test_model", TokensUsage(prompt_tokens=20, completion_tokens=10))
        assert stats.lifecycle_total_data["test_provider"]["test_model"].usage.prompt_tokens == 30

    def test_multiple_providers_tracked_separately(self):
        stats = SessionUsageStats()
        stats.add_stats("a", "m1", TokensUsage(prompt_tokens=100, completion_tokens=50))
        stats.add_stats("b", "m2", TokensUsage(prompt_tokens=200, completion_tokens=100))
        assert stats.lifecycle_total_data["a"]["m1"].usage.prompt_tokens == 100
        assert stats.lifecycle_total_data["b"]["m2"].usage.prompt_tokens == 200

    def test_begin_invocation_clears_current_but_keeps_lifecycle(self):
        stats = SessionUsageStats()
        stats.add_stats("p", "m", TokensUsage(prompt_tokens=10, completion_tokens=5))
        stats.begin_invocation()
        assert stats.current_invocation_data == {}
        assert stats.lifecycle_total_data["p"]["m"].usage.prompt_tokens == 10


# ── Session.create ────────────────────────────────────────────────────────────

class TestSessionCreate:
    async def test_id_is_set(self):
        s = await _make_session()
        assert s.id == "sess-1"

    async def test_created_at_is_datetime(self):
        s = await _make_session()
        assert isinstance(s.created_at, datetime)

    async def test_completion_config_is_set(self):
        cfg = _config()
        s = await _make_session(cfg=cfg)
        assert s.completion_config is cfg

    async def test_statistics_initially_falsy(self):
        s = await _make_session()
        assert not s.statistics

    async def test_messages_initially_empty(self):
        s = await _make_session()
        assert s.messages == []

    async def test_statistics_returns_session_usage_stats(self):
        s = await _make_session()
        assert isinstance(s.statistics, SessionUsageStats)

    async def test_message_context_strategy_property_returns_strategy(self):
        s = await _make_session(strategy_type="dummy")
        strategy = s.message_context_strategy
        assert strategy is not None
        assert strategy.strategy_type == "dummy"

    async def test_message_context_strategy_property_returns_strategy_sliding_window(self):
        s = await _make_session(strategy_type="sliding_window")
        assert s.message_context_strategy.strategy_type == "sliding_window"


# ── Session.acompletion ───────────────────────────────────────────────────────

class TestSessionAcompletion:
    async def test_yields_text_chunk_events(self):
        s = await _make_session(llm=_make_llm(["Hello", " world"]))
        events = [e async for e in s.acompletion("hi", False)]
        text_events = [e for e in events if isinstance(e, SessionTextChunkEvent)]
        assert len(text_events) == 2
        assert text_events[0].text == "Hello"
        assert text_events[1].text == " world"

    async def test_yields_done_event_at_end(self):
        s = await _make_session()
        events = [e async for e in s.acompletion("hi", False)]
        done_events = [e for e in events if isinstance(e, SessionCompletionDoneEvent)]
        assert len(done_events) == 1

    async def test_done_event_has_stop_reason(self):
        s = await _make_session()
        events = [e async for e in s.acompletion("hi", False)]
        done = next(e for e in events if isinstance(e, SessionCompletionDoneEvent))
        assert done.stop_reason == StopReason.STOP

    async def test_done_event_contains_statistics(self):
        s = await _make_session()
        events = [e async for e in s.acompletion("hi", False)]
        done = next(e for e in events if isinstance(e, SessionCompletionDoneEvent))
        assert done.statistics is not None

    async def test_done_event_statistics_is_current_invocation(self):
        """SessionCompletionDoneEvent.statistics is current_invocation_data, not lifecycle."""
        s = await _make_session()
        # First completion
        async for _ in s.acompletion("first", False):
            pass
        # Second completion — done.statistics should reflect only this invocation
        events = [e async for e in s.acompletion("second", False)]
        done = next(e for e in events if isinstance(e, SessionCompletionDoneEvent))
        # current invocation has only this call's stats
        assert done.statistics is not None
        assert done.statistics["test_provider"]["test_model"].usage.prompt_tokens == 10

    async def test_appends_user_and_assistant_messages(self):
        llm = _make_llm(["response"])
        s = await _make_session(llm=llm)
        async for _ in s.acompletion("question", False):
            pass
        records = s._message_context_strategy.get_history()
        assert records[0].message["role"] == "user"
        assert records[0].message["content"] == "question"
        assert records[1].message["role"] == "assistant"
        assert records[1].message["content"] == "response"

    async def test_statistics_updated_after_completion(self):
        s = await _make_session()
        async for _ in s.acompletion("prompt", False):
            pass
        assert s.statistics  # Non-empty

    async def test_multiple_completions_accumulate_lifecycle_statistics(self):
        s = await _make_session()
        async for _ in s.acompletion("first", False):
            pass
        async for _ in s.acompletion("second", False):
            pass
        # Two completions, each with prompt_tokens=10 → lifecycle total should be 20
        assert s.statistics.lifecycle_total_data["test_provider"]["test_model"].usage.prompt_tokens == 20

    async def test_acompletion_passes_get_context_to_llm(self):
        """acompletion() passes get_context() output (dicts) to the LLM port, not get_history()."""
        captured_messages = []
        llm = MagicMock(spec=ILlmPort)

        async def _acompletion(full_messages, completion_config, is_stream_prefered):
            captured_messages.extend(full_messages)
            yield TextChunkEvent(text="answer")
            yield CompletionDoneEvent(
                provider="test_provider",
                model="test_model",
                tokens_usage=TokensUsage(prompt_tokens=10, completion_tokens=5),
                stop_reason=StopReason.STOP,
                elapsed_s=1,
            )

        llm.acompletion = _acompletion
        s = await _make_session(llm=llm)
        async for _ in s.acompletion("hello", False):
            pass
        # get_context() returns dicts, not MessageRecord objects
        assert len(captured_messages) > 0
        assert all(isinstance(m, dict) for m in captured_messages)
        assert any(m.get("role") == "user" and m.get("content") == "hello" for m in captured_messages)

    async def test_elapsed_seconds_in_done_event(self):
        s = await _make_session()
        events = [e async for e in s.acompletion("hi", False)]
        done = next(e for e in events if isinstance(e, SessionCompletionDoneEvent))
        assert done.elapsed_s >= 0

    async def test_no_billing_event_cost_is_none(self):
        """Without ModelBilling configured, cost is None."""
        s = await _make_session(llm=_make_llm())
        async for _ in s.acompletion("hi", False):
            pass
        cost = s.statistics.lifecycle_total_data["test_provider"]["test_model"].cost
        assert cost is None

    async def test_begin_invocation_called_before_each_completion(self):
        """Verify current_invocation_data is reset between completions."""
        s = await _make_session()
        async for _ in s.acompletion("first", False):
            pass
        async for _ in s.acompletion("second", False):
            pass
        # After second call, current_invocation_data reflects only 2nd call
        second_current = s.statistics.current_invocation_data
        assert second_current["test_provider"]["test_model"].usage.prompt_tokens == 10


# ── Session.set_message_context_strategy ─────────────────────────────────────

class TestSessionSetMessageContextStrategy:
    async def test_switches_strategy_type(self):
        llm = _make_llm()
        s = await _make_session(llm=llm)
        new_strategy = SlidingWindowStrategy(
            window_size=5, llm=llm, completion_config=_config()
        )
        await s.set_message_context_strategy(new_strategy)
        assert s._message_context_strategy.strategy_type == "sliding_window"

    async def test_preserves_existing_records(self):
        llm = _make_llm(["reply"])
        s = await _make_session(llm=llm)
        async for _ in s.acompletion("hello", False):
            pass
        existing_count = len(s._message_context_strategy.get_history())

        new_strategy = DummyStrategy(llm=_make_llm(), completion_config=_config())
        await s.set_message_context_strategy(new_strategy)

        assert len(s._message_context_strategy.get_history()) == existing_count

    async def test_set_strategy_transplants_records_via_get_history(self):
        """set_message_context_strategy reads existing records via get_history() (list[MessageRecord])."""
        llm = _make_llm(["reply"])
        s = await _make_session(llm=llm)
        async for _ in s.acompletion("hello", False):
            pass
        # get_history() returns MessageRecord objects
        from server.application.domain.model.context_strategy import MessageRecord
        old_records = s._message_context_strategy.get_history()
        assert all(isinstance(r, MessageRecord) for r in old_records)

        new_strategy = DummyStrategy(llm=_make_llm(), completion_config=_config())
        await s.set_message_context_strategy(new_strategy)
        # Records from old strategy are preserved in the new one
        new_records = s._message_context_strategy.get_history()
        assert len(new_records) == len(old_records)
        assert all(isinstance(r, MessageRecord) for r in new_records)

    async def test_new_strategy_still_accumulates_stats(self):
        s = await _make_session()
        new_strategy = DummyStrategy(llm=_make_llm(), completion_config=_config())
        await s.set_message_context_strategy(new_strategy)

        async for _ in s.acompletion("hi", False):
            pass
        assert s.statistics


# ── SessionState validation ───────────────────────────────────────────────────

class TestSessionState:
    def test_all_fields_accessible_when_constructed(self):
        cfg = _config()
        state = SessionState(
            id="sess-1",
            created_at=datetime.now(),
            completion_config=cfg,
            strategy_type="dummy",
            strategy_completion_config=cfg,
        )
        assert state.id == "sess-1"
        assert state.completion_config == cfg
        assert state.strategy_type == "dummy"
        assert state.strategy_completion_config == cfg

    def test_strategy_records_defaults_to_empty_list(self):
        cfg = _config()
        state = SessionState(
            id="sess-1",
            created_at=datetime.now(),
            completion_config=cfg,
            strategy_type="dummy",
            strategy_completion_config=cfg,
        )
        assert state.strategy_records == []

    def test_statistics_defaults_to_none(self):
        cfg = _config()
        state = SessionState(
            id="sess-1",
            created_at=datetime.now(),
            completion_config=cfg,
            strategy_type="dummy",
            strategy_completion_config=cfg,
        )
        assert state.statistics is None

    def test_empty_id_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SessionState(
                id="",
                created_at=datetime.now(),
                completion_config=_config(),
                strategy_type="dummy",
                strategy_completion_config=_config(),
            )

    def test_strategy_metadata_defaults_to_empty_dict(self):
        cfg = _config()
        state = SessionState(
            id="sess-1",
            created_at=datetime.now(),
            completion_config=cfg,
            strategy_type="sliding_window",
            strategy_completion_config=cfg,
        )
        assert state.strategy_metadata == {}
