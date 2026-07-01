"""Tests for the AI Brain module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import MagicMock, patch, PropertyMock
import random

import pytest

from simulator.ai.ai_brain import AIBrain
from simulator.config import SimulatorConfig, AIConfig
from simulator.generators.base import ActivityEvent
from simulator.scheduler import ScheduledAction


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

class _FakeGenerator:
    """Minimal generator stub for testing."""

    def __init__(self, gen_type: str, actions: list[str]):
        self._gen_type = gen_type
        self._actions = actions

    @property
    def generator_type(self) -> str:
        return self._gen_type

    def get_available_actions(self) -> list[str]:
        return list(self._actions)

    def is_available(self) -> bool:
        return True


@pytest.fixture
def mock_generators() -> dict[str, _FakeGenerator]:
    return {
        "mouse": _FakeGenerator("mouse", ["move_realistic", "click_left"]),
        "keyboard": _FakeGenerator("keyboard", ["type_text"]),
    }


@pytest.fixture
def ai_config() -> AIConfig:
    return AIConfig(
        api_key="test-key-12345",
        model="test/model",
        max_api_calls=10,
        context_window=5,
        thinking_delay_min=0.1,
        thinking_delay_max=0.2,
    )


@pytest.fixture
def sim_config(ai_config) -> SimulatorConfig:
    return SimulatorConfig(ai=ai_config)


def _make_mock_response(tool_calls: list[dict[str, Any]] | None = None):
    """Build a mock OpenAI-style API response."""
    mock_resp = MagicMock()

    if tool_calls is None:
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.tool_calls = None
        return mock_resp

    mock_tool_calls = []
    for tc in tool_calls:
        mock_tc = MagicMock()
        mock_tc.function.name = tc["name"]
        mock_tc.function.arguments = json.dumps(tc.get("arguments", {}))
        mock_tool_calls.append(mock_tc)

    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.tool_calls = mock_tool_calls
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: AIBrain initialization
# ---------------------------------------------------------------------------

class TestAIBrainInit:
    """Tests for AIBrain initialization."""

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_initializes_with_config_api_key(self, mock_openai, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        assert brain.api_calls_made == 0
        assert brain.api_calls_remaining == 10
        mock_openai.assert_called_once()

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_initializes_with_env_api_key(self, mock_openai, mock_generators):
        config = SimulatorConfig(ai=AIConfig(api_key=None))

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key-123"}):
            brain = AIBrain(config, mock_generators, random.Random(42))
            assert brain._api_key == "env-key-123"

    def test_raises_without_api_key(self, mock_generators):
        config = SimulatorConfig(ai=AIConfig(api_key=None))

        with patch.dict("os.environ", {}, clear=True):
            # Also clear OPENROUTER_API_KEY if present
            import os
            env = os.environ.copy()
            env.pop("OPENROUTER_API_KEY", None)
            with patch.dict("os.environ", env, clear=True):
                with pytest.raises(ValueError, match="OpenRouter API key"):
                    AIBrain(config, mock_generators, random.Random(42))


# ---------------------------------------------------------------------------
# Tests: decide_next_actions
# ---------------------------------------------------------------------------

class TestDecideNextActions:
    """Tests for the main decision-making method."""

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_returns_actions_from_tool_calls(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        mock_response = _make_mock_response([
            {"name": "mouse__move_realistic"},
            {"name": "keyboard__type_text"},
        ])
        brain._client.chat.completions.create = MagicMock(return_value=mock_response)

        actions = brain.decide_next_actions()

        assert len(actions) == 2
        assert actions[0].generator_type == "mouse"
        assert actions[0].action_name == "move_realistic"
        assert actions[1].generator_type == "keyboard"
        assert actions[1].action_name == "type_text"

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_returns_idle_on_no_tool_calls(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        mock_response = _make_mock_response(tool_calls=None)
        brain._client.chat.completions.create = MagicMock(return_value=mock_response)

        actions = brain.decide_next_actions()

        assert len(actions) == 1
        assert actions[0].generator_type == "idle"

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_increments_api_call_counter(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        mock_response = _make_mock_response([{"name": "mouse__click_left"}])
        brain._client.chat.completions.create = MagicMock(return_value=mock_response)

        brain.decide_next_actions()
        assert brain.api_calls_made == 1

        brain.decide_next_actions()
        assert brain.api_calls_made == 2

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_enforces_max_api_calls_cap(self, mock_openai_cls, mock_generators):
        config = SimulatorConfig(ai=AIConfig(api_key="test", max_api_calls=2))
        brain = AIBrain(config, mock_generators, random.Random(42))

        mock_response = _make_mock_response([{"name": "mouse__click_left"}])
        brain._client.chat.completions.create = MagicMock(return_value=mock_response)

        brain.decide_next_actions()
        brain.decide_next_actions()
        result = brain.decide_next_actions()  # Should be blocked

        assert result == []
        assert brain.api_calls_made == 2

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_handles_api_error_gracefully(self, mock_openai_cls, sim_config, mock_generators):
        from openai import APIError

        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        brain._client.chat.completions.create = MagicMock(
            side_effect=APIError(
                message="Server error",
                request=MagicMock(),
                body=None,
            )
        )

        actions = brain.decide_next_actions()

        # Should return a recovery idle action, not crash
        assert len(actions) == 1
        assert actions[0].generator_type == "idle"
        assert "error" in actions[0].action_name or "recovery" in actions[0].action_name

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_skips_unknown_generator_in_tool_call(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        mock_response = _make_mock_response([
            {"name": "unknown_gen__some_action"},
            {"name": "mouse__click_left"},
        ])
        brain._client.chat.completions.create = MagicMock(return_value=mock_response)

        actions = brain.decide_next_actions()

        # Should skip the unknown generator and return only the valid action
        assert len(actions) == 1
        assert actions[0].generator_type == "mouse"

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_skips_unknown_action_in_tool_call(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        mock_response = _make_mock_response([
            {"name": "mouse__nonexistent_action"},
            {"name": "mouse__click_left"},
        ])
        brain._client.chat.completions.create = MagicMock(return_value=mock_response)

        actions = brain.decide_next_actions()

        assert len(actions) == 1
        assert actions[0].action_name == "click_left"


# ---------------------------------------------------------------------------
# Tests: Meta-tool handling
# ---------------------------------------------------------------------------

class TestMetaToolParsing:
    """Tests for meta-tool (idle/think) parsing."""

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_handles_meta_idle(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        mock_response = _make_mock_response([
            {"name": "meta__idle", "arguments": {"duration_seconds": 10}},
        ])
        brain._client.chat.completions.create = MagicMock(return_value=mock_response)

        actions = brain.decide_next_actions()

        assert len(actions) == 1
        assert actions[0].generator_type == "idle"
        assert actions[0].action_name == "ai_idle"
        assert actions[0].delay == 10.0

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_clamps_meta_idle_duration(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        mock_response = _make_mock_response([
            {"name": "meta__idle", "arguments": {"duration_seconds": 999}},
        ])
        brain._client.chat.completions.create = MagicMock(return_value=mock_response)

        actions = brain.decide_next_actions()

        assert actions[0].delay == 30.0  # Clamped to max


# ---------------------------------------------------------------------------
# Tests: Action history / context
# ---------------------------------------------------------------------------

class TestActionHistory:
    """Tests for action recording and context building."""

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_record_action_result_stores_entry(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        action = ScheduledAction(delay=1.0, generator_type="mouse", action_name="click_left")
        event = ActivityEvent(event_type="mouse_click", action="click_left", success=True)

        brain.record_action_result(action, event)

        assert len(brain._action_history) == 1
        assert brain._action_history[0]["action"] == "mouse.click_left"

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_trims_history_to_context_window(self, mock_openai_cls, mock_generators):
        config = SimulatorConfig(ai=AIConfig(api_key="test", context_window=3))
        brain = AIBrain(config, mock_generators, random.Random(42))

        for i in range(10):
            action = ScheduledAction(delay=1.0, generator_type="mouse", action_name="click_left")
            brain.record_action_result(action)

        assert len(brain._action_history) == 3

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_messages_include_history(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        action = ScheduledAction(delay=1.0, generator_type="mouse", action_name="click_left")
        brain.record_action_result(action)

        messages = brain._build_messages()

        assert len(messages) == 2  # system + user
        assert "click_left" in messages[1]["content"]

    @patch("simulator.ai.ai_brain.OpenAI")
    def test_first_message_is_session_start(self, mock_openai_cls, sim_config, mock_generators):
        brain = AIBrain(sim_config, mock_generators, random.Random(42))

        messages = brain._build_messages()

        assert len(messages) == 2
        assert "starting a new work session" in messages[1]["content"].lower()
