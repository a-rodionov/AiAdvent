"""Unit tests for server.domain.value_objects.completion.

Pure value-object tests: no mocks required — Pydantic validation and the
__copy__ helper are exercised directly.
"""
import pytest
from pydantic import ValidationError

from server.application.domain.model.completion import CompletionConfig, format_completion_config
from server.application.domain.model.session import StopReason
from server.application.domain.model.usage_stats import TokensUsage

# ── StopReason ────────────────────────────────────────────────────────────────

class TestStopReason:
    def test_members_exist(self):
        assert StopReason.STOP == "stop"
        assert StopReason.LENGTH == "length"
        assert StopReason.TOOL_CALLS == "tool_calls"
        assert StopReason.CONTENT_FILTER == "content_filter"

    def test_is_string_enum(self):
        assert isinstance(StopReason.STOP, str)

    def test_comparison_with_string(self):
        assert StopReason.STOP == "stop"


# ── TokensUsage ───────────────────────────────────────────────────────────────

class TestTokensUsage:
    def test_defaults_to_zero(self):
        usage = TokensUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0

    def test_accepts_positive_values(self):
        usage = TokensUsage(prompt_tokens=10, completion_tokens=5)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 5

    def test_rejects_negative_prompt_tokens(self):
        with pytest.raises(ValidationError):
            TokensUsage(prompt_tokens=-1)

    def test_rejects_negative_completion_tokens(self):
        with pytest.raises(ValidationError):
            TokensUsage(completion_tokens=-1)

    def test_zero_is_valid(self):
        usage = TokensUsage(prompt_tokens=0, completion_tokens=0)
        assert usage.prompt_tokens == 0


# ── CompletionConfig ──────────────────────────────────────────────────────────

class TestCompletionConfig:
    def _minimal(self, **overrides):
        defaults = {"provider": "openai", "model": "gpt-4", "max_tokens": 256}
        defaults.update(overrides)
        return CompletionConfig(**defaults)

    def test_minimal_config_is_valid(self):
        cfg = self._minimal()
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4"
        assert cfg.max_tokens == 256

    def test_empty_provider_raises(self):
        with pytest.raises(ValidationError):
            self._minimal(provider="")

    def test_empty_model_raises(self):
        with pytest.raises(ValidationError):
            self._minimal(model="")

    def test_max_tokens_zero_raises(self):
        with pytest.raises(ValidationError):
            self._minimal(max_tokens=0)

    def test_max_tokens_negative_raises(self):
        with pytest.raises(ValidationError):
            self._minimal(max_tokens=-1)

    def test_temperature_boundaries(self):
        assert self._minimal(temperature=0.0).temperature == 0.0
        assert self._minimal(temperature=1.0).temperature == 1.0

    def test_temperature_above_one_raises(self):
        with pytest.raises(ValidationError):
            self._minimal(temperature=1.01)

    def test_temperature_below_zero_raises(self):
        with pytest.raises(ValidationError):
            self._minimal(temperature=-0.01)

    def test_top_k_zero_is_valid(self):
        assert self._minimal(top_k=0).top_k == 0

    def test_top_k_negative_raises(self):
        with pytest.raises(ValidationError):
            self._minimal(top_k=-1)

    def test_top_p_boundaries(self):
        assert self._minimal(top_p=0.0).top_p == 0.0
        assert self._minimal(top_p=1.0).top_p == 1.0

    def test_top_p_above_one_raises(self):
        with pytest.raises(ValidationError):
            self._minimal(top_p=1.01)

    def test_optional_fields_default_to_none(self):
        cfg = self._minimal()
        assert cfg.system_prompt is None
        assert cfg.system_prompt_path is None
        assert cfg.temperature is None
        assert cfg.top_k is None
        assert cfg.top_p is None
        assert cfg.stop_sequences is None
        assert cfg.output_config is None
        assert cfg.output_config_path is None

    def test_copy_preserves_core_fields(self):
        cfg = self._minimal(
            system_prompt="Be helpful.",
            temperature=0.7,
            stop_sequences=["END"],
        )
        copy = cfg.__copy__()
        assert copy.provider == cfg.provider
        assert copy.model == cfg.model
        assert copy.max_tokens == cfg.max_tokens
        assert copy.temperature == cfg.temperature
        assert copy.stop_sequences == cfg.stop_sequences

    def test_copy_clears_path_fields(self):
        cfg = self._minimal(
            system_prompt_path="/prompts/system.txt",
            output_config_path="/schemas/output.json",
        )
        copy = cfg.__copy__()
        assert copy.system_prompt_path is None
        assert copy.output_config_path is None

    def test_copy_preserves_system_prompt(self):
        cfg = self._minimal(system_prompt="You are a pirate.")
        copy = cfg.__copy__()
        assert copy.system_prompt == "You are a pirate."

    def test_copy_returns_new_instance(self):
        cfg = self._minimal()
        copy = cfg.__copy__()
        assert copy is not cfg



# ── format_completion_config ──────────────────────────────────────────────────

class TestFormatCompletionConfig:
    def test_includes_required_fields(self):
        cfg = CompletionConfig(provider="anthropic", model="claude-3", max_tokens=1024)
        output = format_completion_config(cfg)
        assert "provider" in output
        assert "anthropic" in output
        assert "model" in output
        assert "claude-3" in output
        assert "max_tokens" in output

    def test_omits_none_fields(self):
        cfg = CompletionConfig(provider="p", model="m", max_tokens=10)
        output = format_completion_config(cfg)
        assert "temperature" not in output
        assert "top_k" not in output

    def test_includes_set_optional_fields(self):
        cfg = CompletionConfig(
            provider="p", model="m", max_tokens=10, temperature=0.5, top_k=40
        )
        output = format_completion_config(cfg)
        assert "temperature" in output
        assert "0.5" in output
        assert "top_k" in output
