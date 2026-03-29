"""Unit tests for server.domain.entities.context_strategy.

The strategies depend on ILlmPort only for SummaryStrategy.update_context (lazy summarisation).
All other behaviour is tested without touching the LLM port.
"""
import inspect
import uuid
from unittest.mock import MagicMock

import pytest

from server.application.domain.model.completion import CompletionConfig
from server.application.domain.model.context_strategy import (
    DummyStrategy,
    MessageContextStrategy,
    MessageContextStrategyDefaults,
    MessageContextStrategyFactory,
    MessageRecord,
    SlidingWindowStrategy,
    SummaryStrategy,
)
from server.application.domain.model.context_strategy.summary_strategy import Summary
from server.application.domain.model.session import StopReason
from server.application.domain.model.usage_stats import TokensUsage
from server.application.port.outbound.llm_port import CompletionDoneEvent, ILlmPort, TextChunkEvent

# ── Helpers ───────────────────────────────────────────────────────────────────

def _config():
    return CompletionConfig(provider="p", model="m", max_tokens=100)


def _config_with_prompt(prompt: str):
    return CompletionConfig(provider="p", model="m", max_tokens=100, system_prompt=prompt)


def _make_llm(text_chunks: list[str] | None = None, provider="p", model="m"):
    """Return an ILlmPort mock whose acompletion is an async generator."""
    llm = MagicMock(spec=ILlmPort)

    async def _acompletion(full_messages, completion_config, is_stream_prefered):
        for chunk in (text_chunks or []):
            yield TextChunkEvent(text=chunk)
        yield CompletionDoneEvent(
            provider=provider,
            model=model,
            tokens_usage=TokensUsage(prompt_tokens=10, completion_tokens=5),
            stop_reason=StopReason.STOP,
        )

    llm.acompletion = _acompletion
    return llm


def _record(role="user", content="hello", prev_id=None):
    return MessageRecord(id=uuid.uuid4(), prev_id=prev_id, message={"role": role, "content": content})


# ── MessageRecord ─────────────────────────────────────────────────────────────

class TestMessageRecord:
    def test_fields_accessible(self):
        rec_id = uuid.uuid4()
        prev = uuid.uuid4()
        r = MessageRecord(id=rec_id, prev_id=prev, message={"role": "user", "content": "hi"})
        assert r.id == rec_id
        assert r.prev_id == prev
        assert r.message["role"] == "user"

    def test_prev_id_can_be_none(self):
        r = MessageRecord(id=uuid.uuid4(), prev_id=None, message={"role": "user", "content": "hi"})
        assert r.prev_id is None

    def test_is_named_tuple(self):
        r = _record()
        assert isinstance(r, tuple)


# ── DummyStrategy ─────────────────────────────────────────────────────────────

class TestDummyStrategy:
    def test_strategy_type(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        assert s.strategy_type == "dummy"

    def test_get_metadata_is_empty(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        assert s.get_metadata() == {}

    def test_get_history_empty_when_no_messages(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        assert s.get_history() == []

    def test_get_history_returns_raw_records(self):
        """get_history() returns list[MessageRecord], not dicts."""
        records = [_record("user", "hi"), _record("assistant", "hello")]
        s = DummyStrategy(llm=_make_llm(), completion_config=_config(), records=records)
        history = s.get_history()
        assert len(history) == 2
        assert isinstance(history[0], MessageRecord)
        assert history[0].message["role"] == "user"
        assert history[1].message["role"] == "assistant"

    def test_get_history_does_not_include_system_prompt(self):
        """get_history() returns raw records only — no system prompt injection."""
        cfg = _config_with_prompt("Be concise.")
        s = DummyStrategy(llm=_make_llm(), completion_config=cfg, records=[_record()])
        history = s.get_history()
        # raw records, no system message
        assert len(history) == 1
        assert isinstance(history[0], MessageRecord)

    def test_get_records_no_longer_exists(self):
        """get_records() must NOT exist on any strategy."""
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        assert not hasattr(s, "get_records")

    async def test_get_context_returns_dicts(self):
        """get_context() returns list[dict[str, str]] for the LLM."""
        records = [_record("user", "hi"), _record("assistant", "hello")]
        s = DummyStrategy(llm=_make_llm(), completion_config=_config(), records=records)
        ctx = await s.get_context()
        assert isinstance(ctx[0], dict)
        assert ctx[0]["role"] == "user"

    async def test_get_context_no_system_prompt_without_config(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config(), records=[_record()])
        ctx = await s.get_context()
        assert ctx[0]["role"] != "system"

    async def test_get_context_empty_when_no_records(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        assert await s.get_context() == []

    async def test_add_user_query_appends_record(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        await s.add_user_query("What is 2+2?")
        records = s.get_history()
        assert len(records) == 1
        assert records[0].message == {"role": "user", "content": "What is 2+2?"}

    async def test_add_model_response_appends_record(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        await s.add_model_response("It's 4.")
        records = s.get_history()
        assert len(records) == 1
        assert records[0].message == {"role": "assistant", "content": "It's 4."}

    async def test_records_linked_via_prev_id(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        await s.add_user_query("first")
        await s.add_model_response("second")
        records = s.get_history()
        assert records[1].prev_id == records[0].id

    async def test_first_record_has_no_prev_id(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        await s.add_user_query("first")
        assert s.get_history()[0].prev_id is None

    def test_no_token_usage_handler_mechanism(self):
        """Verify no OnTokenUsage, _emit_token_usage, or _token_usage_handlers exist."""
        s = DummyStrategy(llm=_make_llm(), completion_config=_config())
        assert not hasattr(s, "OnTokenUsage")
        assert not hasattr(s, "_emit_token_usage")
        assert not hasattr(s, "_token_usage_handlers")

    def test_llm_property(self):
        llm = _make_llm()
        s = DummyStrategy(llm=llm, completion_config=_config())
        assert s.llm is llm

    def test_completion_config_property(self):
        cfg = _config()
        s = DummyStrategy(llm=_make_llm(), completion_config=cfg)
        assert s.completion_config is cfg

    def test_get_history_returns_copy(self):
        s = DummyStrategy(llm=_make_llm(), completion_config=_config(), records=[_record()])
        r1 = s.get_history()
        r2 = s.get_history()
        assert r1 is not r2


# ── SlidingWindowStrategy ─────────────────────────────────────────────────────

class TestSlidingWindowStrategy:
    def test_strategy_type(self):
        s = SlidingWindowStrategy(window_size=3, llm=_make_llm(), completion_config=_config())
        assert s.strategy_type == "sliding_window"

    def test_window_size_zero_raises(self):
        with pytest.raises(ValueError, match="window_size must be >= 1"):
            SlidingWindowStrategy(window_size=0, llm=_make_llm(), completion_config=_config())

    def test_window_size_negative_raises(self):
        with pytest.raises(ValueError):
            SlidingWindowStrategy(window_size=-5, llm=_make_llm(), completion_config=_config())

    def test_get_metadata_contains_window_size(self):
        s = SlidingWindowStrategy(window_size=4, llm=_make_llm(), completion_config=_config())
        assert s.get_metadata() == {"window_size": 4}

    def test_get_records_no_longer_exists(self):
        """get_records() must NOT exist on SlidingWindowStrategy."""
        s = SlidingWindowStrategy(window_size=3, llm=_make_llm(), completion_config=_config())
        assert not hasattr(s, "get_records")

    async def test_does_not_trim_when_within_window(self):
        """get_history() returns all records; windowing only applies in get_context()."""
        records = [_record() for _ in range(3)]
        s = SlidingWindowStrategy(window_size=5, llm=_make_llm(), completion_config=_config(), records=records)
        assert len(s.get_history()) == 3
        ctx = await s.get_context()
        assert len(ctx) == 3  # all 3 fit in window of 5

    async def test_trims_oldest_records_when_over_window(self):
        """get_history() returns ALL records; get_context() returns only last window_size."""
        records = [_record(content=str(i)) for i in range(10)]
        s = SlidingWindowStrategy(window_size=3, llm=_make_llm(), completion_config=_config(), records=records)
        # get_history() returns full untrimmed list
        assert len(s.get_history()) == 10
        # get_context() returns only the last window_size
        ctx = await s.get_context()
        assert len(ctx) == 3
        assert ctx[0]["content"] == "7"
        assert ctx[2]["content"] == "9"

    async def test_get_history_returns_raw_records(self):
        """get_history() returns ALL MessageRecord objects, not windowed."""
        records = [_record(content=str(i)) for i in range(5)]
        s = SlidingWindowStrategy(window_size=2, llm=_make_llm(), completion_config=_config(), records=records)
        history = s.get_history()
        assert len(history) == 5  # full untrimmed count
        assert all(isinstance(r, MessageRecord) for r in history)

    async def test_get_context_returns_last_window_size_dicts(self):
        """get_context() returns only the last window_size message dicts."""
        records = [_record(content=str(i)) for i in range(5)]
        s = SlidingWindowStrategy(window_size=3, llm=_make_llm(), completion_config=_config(), records=records)
        ctx = await s.get_context()
        # 5 records, window=3 → last 3 (indices 2,3,4)
        assert len(ctx) == 3
        assert all(isinstance(msg, dict) for msg in ctx)
        assert ctx[0]["content"] == "2"
        assert ctx[2]["content"] == "4"

    async def test_add_user_query_full_history_windowed_context(self):
        """get_history() returns every appended record; get_context() windows to last window_size."""
        records = [_record() for _ in range(4)]
        s = SlidingWindowStrategy(window_size=3, llm=_make_llm(), completion_config=_config(), records=records)
        await s.add_user_query("new message")
        # get_history() has all 5 records (4 initial + 1 added)
        assert len(s.get_history()) == 5
        # get_context() returns only the last window_size=3
        ctx = await s.get_context()
        assert len(ctx) == 3
        assert ctx[-1]["content"] == "new message"

    async def test_create_with_exact_window_size_records(self):
        records = [_record() for _ in range(3)]
        s = SlidingWindowStrategy(window_size=3, llm=_make_llm(), completion_config=_config(), records=records)
        assert len(s.get_history()) == 3


# ── SummaryStrategy ───────────────────────────────────────────────────────────

class TestSummaryStrategy:
    def test_window_size_zero_raises(self):
        with pytest.raises(ValueError, match="window_size must be >= 1"):
            SummaryStrategy(
                window_size=0, summarization_prompt="Summarize: %s", llm=_make_llm(), completion_config=_config()
            )

    def test_llm_none_raises(self):
        with pytest.raises(ValueError, match="LlmPort object is None"):
            SummaryStrategy(
                window_size=4, summarization_prompt="Summarize: %s", llm=None, completion_config=_config()
            )

    def test_empty_summarization_prompt_raises(self):
        with pytest.raises(ValueError, match="summarization_prompt must be not empty string"):
            SummaryStrategy(
                window_size=4, summarization_prompt="", llm=_make_llm(), completion_config=_config()
            )

    def test_none_summarization_prompt_raises(self):
        with pytest.raises(ValueError, match="summarization_prompt must be not empty string"):
            SummaryStrategy(
                window_size=4, summarization_prompt=None, llm=_make_llm(), completion_config=_config()  # type: ignore[arg-type]
            )

    def test_strategy_type(self):
        s = SummaryStrategy(window_size=4, summarization_prompt="Summarize: %s", llm=_make_llm(), completion_config=_config())
        assert s.strategy_type == "summary"

    def test_get_records_no_longer_exists(self):
        """get_records() must NOT exist on SummaryStrategy."""
        s = SummaryStrategy(window_size=4, summarization_prompt="Summarize: %s", llm=_make_llm(), completion_config=_config())
        assert not hasattr(s, "get_records")

    def test_get_metadata_contains_window_and_summary_text(self):
        """get_metadata() uses 'summary_text' key (not 'summary')."""
        anchor = uuid.uuid4()
        s = SummaryStrategy(
            window_size=4,
            summarization_prompt="Summarize this.",
            llm=_make_llm(),
            completion_config=_config(),
            summary=Summary(text="prior context", anchor_id=anchor),
        )
        meta = s.get_metadata()
        assert meta["window_size"] == 4
        assert meta["summary_text"] == "prior context"
        assert meta["summary_anchor_id"] == str(anchor)
        assert meta["summarization_prompt"] == "Summarize this."
        # Old key must NOT exist
        assert "summary" not in meta

    def test_get_metadata_anchor_none_when_no_summary(self):
        s = SummaryStrategy(window_size=4, summarization_prompt="Summarize: %s", llm=_make_llm(), completion_config=_config())
        meta = s.get_metadata()
        assert meta["summary_text"] == ""
        assert meta["summary_anchor_id"] is None

    def test_summary_namedtuple_identity(self):
        """Summary is a NamedTuple with text and anchor_id fields."""
        anchor = uuid.uuid4()
        s = Summary(text="hello", anchor_id=anchor)
        assert s.text == "hello"
        assert s.anchor_id == anchor
        assert isinstance(s, tuple)

    def test_summary_anchor_id_can_be_none(self):
        s = Summary(text="", anchor_id=None)
        assert s.anchor_id is None

    async def test_create_does_not_summarize_when_below_window(self):
        """No summarisation when count_since_anchor < window_size (lazy — only fires in update_context)."""
        records = [_record() for _ in range(3)]
        s = SummaryStrategy(
            window_size=5, summarization_prompt="Summarize: %s", llm=_make_llm(["summary text"]),
            completion_config=_config(), records=records
        )
        assert len(s.get_history()) == 3
        assert s.get_metadata()["summary_text"] == ""

    async def test_apply_strategy_fires_at_window_size(self):
        """Trigger condition is count_since_anchor >= window_size; fires lazily in update_context()."""
        # Exactly window_size records → should trigger on update_context()
        records = [_record(content=str(i)) for i in range(4)]
        llm = _make_llm(text_chunks=["fired summary"])
        s = SummaryStrategy(
            window_size=4, summarization_prompt="Summarize: %s", llm=llm,
            completion_config=_config(), records=records
        )
        await s.update_context()
        assert s.get_metadata()["summary_text"] == "fired summary"

    async def test_apply_strategy_fires_above_window_size(self):
        """Trigger also fires when count_since_anchor > window_size."""
        records = [_record(content=str(i)) for i in range(6)]
        llm = _make_llm(text_chunks=["This is the summary."])
        s = SummaryStrategy(
            window_size=4, summarization_prompt="Summarize: %s", llm=llm,
            completion_config=_config(), records=records
        )
        await s.update_context()
        assert s.get_metadata()["summary_text"] == "This is the summary."

    async def test_records_preserved_after_summarisation(self):
        """Records are NOT cleared after summarisation."""
        records = [_record(content=str(i)) for i in range(6)]
        llm = _make_llm(text_chunks=["summary result"])
        s = SummaryStrategy(
            window_size=4, summarization_prompt="Summarize: %s", llm=llm,
            completion_config=_config(), records=records
        )
        await s.update_context()
        # Records must be preserved (not cleared)
        history = s.get_history()
        assert len(history) == 6
        assert all(isinstance(r, MessageRecord) for r in history)

    async def test_anchor_updated_after_summarisation(self):
        """After summarisation, anchor_id points to the last record's id."""
        records = [_record(content=str(i)) for i in range(4)]
        last_id = records[-1].id
        llm = _make_llm(text_chunks=["anchor summary"])
        s = SummaryStrategy(
            window_size=4, summarization_prompt="Summarize: %s", llm=llm,
            completion_config=_config(), records=records
        )
        await s.update_context()
        meta = s.get_metadata()
        assert meta["summary_anchor_id"] == str(last_id)

    async def test_get_context_without_anchor_returns_all_records_as_dicts(self):
        """When no anchor exists, _get_context() returns all record messages."""
        records = [_record("user", "hi"), _record("assistant", "hello")]
        s = SummaryStrategy(
            window_size=4, summarization_prompt="Summarize: %s", llm=_make_llm(),
            completion_config=_config(), records=records
        )
        ctx = await s.get_context()
        # No system prompt configured, no anchor → just the 2 record dicts
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"
        assert ctx[0]["content"] == "hi"

    async def test_get_context_with_anchor_prepends_summary_text(self):
        """When anchor exists, _get_context() prepends summary as user message."""
        anchor = uuid.uuid4()
        anchor_record = MessageRecord(id=anchor, prev_id=None, message={"role": "user", "content": "old"})
        new_record = _record("user", "new message")
        s = SummaryStrategy(
            window_size=4,
            summarization_prompt="Summarize: %s",
            llm=_make_llm(),
            completion_config=_config(),
            records=[anchor_record, new_record],
            summary=Summary(text="old context", anchor_id=anchor),
        )
        ctx = await s.get_context()
        # Anchor record is "consumed" by summary; only records after anchor + summary text
        assert ctx[0] == {"role": "user", "content": "old context"}
        assert ctx[-1]["content"] == "new message"

    async def test_get_context_with_anchor(self):
        """get_context() prepends summary, then records after anchor."""
        cfg = _config_with_prompt("System instruction.")
        anchor = uuid.uuid4()
        anchor_record = MessageRecord(id=anchor, prev_id=None, message={"role": "user", "content": "old"})
        new_record = _record("user", "new")
        s = SummaryStrategy(
            window_size=4,
            summarization_prompt="Summarize: %s",
            llm=_make_llm(),
            completion_config=cfg,
            records=[anchor_record, new_record],
            summary=Summary(text="summary text", anchor_id=anchor),
        )
        ctx = await s.get_context()
        assert ctx[0] == {"role": "user", "content": "summary text"}
        assert ctx[1]["content"] == "new"

    async def test_get_context_skips_summary_text_when_empty(self):
        """_get_context() does not prepend a user message when summary text is empty."""
        s = SummaryStrategy(
            window_size=4, summarization_prompt="Summarize: %s", llm=_make_llm(), completion_config=_config(),
            records=[_record("user", "hi")]
        )
        ctx = await s.get_context()
        assert len(ctx) == 1
        assert ctx[0]["content"] == "hi"

    async def test_trigger_below_window_after_anchor(self):
        """Records below window_size after anchor → no summarisation."""
        anchor = uuid.uuid4()
        anchor_record = MessageRecord(id=anchor, prev_id=None, message={"role": "user", "content": "anchored"})
        # Only 2 records after anchor, window=4 → no trigger
        new_records = [_record(content=str(i)) for i in range(2)]
        llm = _make_llm(text_chunks=["should not appear"])
        s = SummaryStrategy(
            window_size=4,
            summarization_prompt="Summarize: %s",
            llm=llm,
            completion_config=_config(),
            records=[anchor_record, *new_records],
            summary=Summary(text="existing summary", anchor_id=anchor),
        )
        # Trigger via update_context() (lazy semantics)
        await s.update_context()
        # Summary should be unchanged — no new summarisation
        assert s.get_metadata()["summary_text"] == "existing summary"

    async def test_trigger_at_window_after_anchor(self):
        """Records at exactly window_size after anchor → summarisation fires."""
        anchor = uuid.uuid4()
        anchor_record = MessageRecord(id=anchor, prev_id=None, message={"role": "user", "content": "anchored"})
        new_records = [_record(content=str(i)) for i in range(4)]  # exactly window_size=4
        llm = _make_llm(text_chunks=["new summary"])
        s = SummaryStrategy(
            window_size=4,
            summarization_prompt="Summarize: %s",
            llm=llm,
            completion_config=_config(),
            records=[anchor_record, *new_records],
            summary=Summary(text="existing summary", anchor_id=anchor),
        )
        await s.update_context()
        assert s.get_metadata()["summary_text"] == "new summary"

    async def test_records_preserved_across_multiple_summarisations(self):
        """Records accumulate and are never cleared."""
        llm = _make_llm(text_chunks=["summary"])
        s = SummaryStrategy(
            window_size=2, summarization_prompt="Summarize: %s", llm=llm,
            completion_config=_config(), records=[]
        )
        await s.add_user_query("msg1")
        await s.add_model_response("reply1")
        # At 2 records from anchor (None), summarisation fires on update_context()
        await s.update_context()
        initial_count = len(s.get_history())
        await s.add_user_query("msg2")
        await s.add_model_response("reply2")
        # Records keep accumulating
        assert len(s.get_history()) >= initial_count

    async def test_get_context_no_emit_token_usage_call(self):
        """SummaryStrategy.update_context has no _emit_token_usage — decorator handles stats."""
        import inspect
        source = inspect.getsource(SummaryStrategy.update_context)
        assert "_emit_token_usage" not in source

    async def test_summarization_updates_summary_text(self):
        """Summarization occurs when records reach window_size; fires lazily in update_context()."""
        records = [_record(content=str(i)) for i in range(6)]
        llm = _make_llm(text_chunks=["summary result"], provider="prov", model="mod")
        s = SummaryStrategy(
            window_size=4, summarization_prompt="Summarize: %s", llm=llm,
            completion_config=_config(), records=records
        )
        # Trigger summarisation lazily via update_context()
        await s.update_context()
        # Records are preserved and summary is set
        assert len(s.get_history()) == 6
        assert s.get_metadata()["summary_text"] == "summary result"


# ── MessageContextStrategyFactory ─────────────────────────────────────────────

class TestMessageContextStrategyFactory:
    def test_build_dummy(self):
        strategy = MessageContextStrategyFactory.build(
            "dummy", {}, [], _make_llm(), _config()
        )
        assert isinstance(strategy, DummyStrategy)

    def test_build_sliding_window_default_window(self):
        strategy = MessageContextStrategyFactory.build(
            "sliding_window", {}, [], _make_llm(), _config()
        )
        assert isinstance(strategy, SlidingWindowStrategy)
        assert strategy.get_metadata()["window_size"] == 8

    def test_build_sliding_window_custom_window(self):
        strategy = MessageContextStrategyFactory.build(
            "sliding_window", {"window_size": 5}, [], _make_llm(), _config()
        )
        assert strategy.get_metadata()["window_size"] == 5

    def test_build_summary_default_window(self):
        strategy = MessageContextStrategyFactory.build(
            "summary", {"summarization_prompt": "Summarize: %s"}, [], _make_llm(), _config()
        )
        assert isinstance(strategy, SummaryStrategy)
        assert strategy.get_metadata()["window_size"] == 4

    def test_build_summary_restores_summary_text(self):
        """Factory reads 'summary_text' key (not 'summary')."""
        strategy = MessageContextStrategyFactory.build(
            "summary", {"window_size": 3, "summary_text": "prior", "summarization_prompt": "Summarize: %s"}, [], _make_llm(), _config()
        )
        assert strategy.get_metadata()["summary_text"] == "prior"

    def test_build_summary_restores_anchor_id(self):
        """Factory parses summary_anchor_id as UUID."""
        anchor = uuid.uuid4()
        strategy = MessageContextStrategyFactory.build(
            "summary",
            {"window_size": 3, "summary_text": "prior", "summary_anchor_id": str(anchor), "summarization_prompt": "Summarize: %s"},
            [],
            _make_llm(),
            _config(),
        )
        assert strategy.get_metadata()["summary_anchor_id"] == str(anchor)

    def test_build_summary_anchor_none_when_not_provided(self):
        strategy = MessageContextStrategyFactory.build(
            "summary", {"summary_text": "", "summarization_prompt": "Summarize: %s"}, [], _make_llm(), _config()
        )
        assert strategy.get_metadata()["summary_anchor_id"] is None

    def test_build_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy type"):
            MessageContextStrategyFactory.build(
                "nonexistent", {}, [], _make_llm(), _config()
            )

    def test_build_summary_no_summarization_prompt_raises(self):
        """Factory defaults summarization_prompt to '' when absent; SummaryStrategy rejects it."""
        with pytest.raises(ValueError, match="summarization_prompt must be not empty string"):
            MessageContextStrategyFactory.build(
                "summary", {}, [], _make_llm(), _config()
            )

    def test_get_metadata_round_trip_summary(self):
        """get_metadata() output can be fed back into factory.build() to restore state."""
        anchor = uuid.uuid4()
        anchor_record = MessageRecord(id=anchor, prev_id=None, message={"role": "user", "content": "a"})
        extra = _record("user", "b")
        original = SummaryStrategy(
            window_size=3,
            summarization_prompt="Summarize it.",
            llm=_make_llm(),
            completion_config=_config(),
            records=[anchor_record, extra],
            summary=Summary(text="round trip text", anchor_id=anchor),
        )
        meta = original.get_metadata()
        restored = MessageContextStrategyFactory.build(
            "summary", meta, [anchor_record, extra], _make_llm(), _config()
        )
        assert restored.get_metadata()["summary_text"] == "round trip text"
        assert restored.get_metadata()["summary_anchor_id"] == str(anchor)
        assert restored.get_metadata()["window_size"] == 3
        assert restored.get_metadata()["summarization_prompt"] == "Summarize it."

    def test_default_method_does_not_exist(self):
        assert not hasattr(MessageContextStrategyFactory, "default")


# ── MessageContextStrategyDefaults ────────────────────────────────────────────

class TestMessageContextStrategyDefaults:
    def test_type_and_completion_config_accessible(self):
        cfg = _config()
        defaults = MessageContextStrategyDefaults(type="dummy", completion_config=cfg)
        assert defaults.type == "dummy"
        assert defaults.completion_config == cfg

    def test_metadata_defaults_to_empty_dict(self):
        defaults = MessageContextStrategyDefaults(type="sliding_window", completion_config=_config())
        assert defaults.metadata == {}

    def test_metadata_carries_type_specific_values(self):
        defaults = MessageContextStrategyDefaults(
            type="summary",
            completion_config=_config(),
            metadata={"window_size": 4, "summarization_prompt": "Summarize: {{CHAT_HISTORY}}"},
        )
        assert defaults.metadata["window_size"] == 4
        assert defaults.metadata["summarization_prompt"] == "Summarize: {{CHAT_HISTORY}}"

    def test_empty_type_raises_validation_error(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MessageContextStrategyDefaults(type="", completion_config=_config())


# ── Section 9: TDD additions for new requirements ────────────────────────────


class TestNoCreateClassmethod:
    """9.4 — SlidingWindowStrategy and SummaryStrategy must not have a create classmethod."""

    def test_sliding_window_has_no_create(self):
        assert not hasattr(SlidingWindowStrategy, "create")

    def test_summary_has_no_create(self):
        assert not hasattr(SummaryStrategy, "create")


class TestFactoryBuildIsSync:
    """9.5 — MessageContextStrategyFactory.build must be a sync function."""

    def test_build_is_not_coroutine_function(self):
        assert inspect.iscoroutinefunction(MessageContextStrategyFactory.build) is False


class TestGetContextAndUpdateContextAreAsync:
    """9.6 — get_context and update_context must be async on base and all subclasses."""

    def test_base_get_context_is_async(self):
        assert inspect.iscoroutinefunction(MessageContextStrategy.get_context) is True

    def test_base_update_context_is_async(self):
        assert inspect.iscoroutinefunction(MessageContextStrategy.update_context) is True

    def test_dummy_get_context_is_async(self):
        assert inspect.iscoroutinefunction(DummyStrategy.get_context) is True

    def test_dummy_update_context_is_async(self):
        assert inspect.iscoroutinefunction(DummyStrategy.update_context) is True

    def test_sliding_window_get_context_is_async(self):
        assert inspect.iscoroutinefunction(SlidingWindowStrategy.get_context) is True

    def test_sliding_window_update_context_is_async(self):
        assert inspect.iscoroutinefunction(SlidingWindowStrategy.update_context) is True

    def test_summary_get_context_is_async(self):
        assert inspect.iscoroutinefunction(SummaryStrategy.get_context) is True

    def test_summary_update_context_is_async(self):
        assert inspect.iscoroutinefunction(SummaryStrategy.update_context) is True


class TestSummaryStrategyLazySummarisation:
    """9.7 — summarisation must fire lazily inside update_context(), not inside add_*."""

    async def test_acompletion_not_called_before_update_context(self):
        """Appending records up to window_size must not trigger LLM call."""
        call_count = 0
        llm = MagicMock(spec=ILlmPort)
        initial_summary: Summary | None = None

        async def _acompletion(full_messages, completion_config, is_stream_prefered):
            nonlocal call_count
            call_count += 1
            yield TextChunkEvent(text="summary result")
            yield CompletionDoneEvent(
                provider="p",
                model="m",
                tokens_usage=TokensUsage(prompt_tokens=10, completion_tokens=5),
                stop_reason=StopReason.STOP,
            )

        llm.acompletion = _acompletion

        window_size = 3
        s = SummaryStrategy(
            window_size=window_size,
            summarization_prompt="Summarize: %s",
            llm=llm,
            completion_config=_config(),
            records=[],
        )
        initial_summary = s._summary  # type: ignore[attr-defined]

        # Append window_size records without calling update_context()
        for i in range(window_size):
            if i % 2 == 0:
                await s.add_user_query(f"msg{i}")
            else:
                await s.add_model_response(f"reply{i}")

        # LLM must NOT have been called
        assert call_count == 0
        assert s._summary == initial_summary  # type: ignore[attr-defined]

        # Now trigger via update_context()
        await s.update_context()

        # LLM must have been called exactly once and summary must have rotated
        assert call_count == 1
        assert s._summary is not initial_summary  # type: ignore[attr-defined]
        assert s._summary.text == "summary result"  # type: ignore[attr-defined]


class TestSlidingWindowFullHistory:
    """9.8 — get_history() returns all records; get_context() returns only last window_size."""

    async def test_full_history_vs_windowed_context(self):
        window_size = 3
        extra = 5
        s = SlidingWindowStrategy(
            window_size=window_size,
            llm=_make_llm(),
            completion_config=_config(),
        )
        for i in range(window_size + extra):
            await s.add_user_query(f"msg{i}")

        assert len(s.get_history()) == window_size + extra
        ctx = await s.get_context()
        assert len(ctx) == window_size

    async def test_full_history_vs_windowed_context_with_system_prompt(self):
        window_size = 4
        extra = 5
        cfg = _config_with_prompt("System prompt.")
        s = SlidingWindowStrategy(
            window_size=window_size,
            llm=_make_llm(),
            completion_config=cfg,
        )
        for i in range(window_size + extra):
            await s.add_user_query(f"msg{i}")

        assert len(s.get_history()) == window_size + extra
        ctx = await s.get_context()
        # window_size messages
        assert len(ctx) == window_size
