"""Tests for the AI tool registry module."""

from __future__ import annotations

import pytest

from simulator.ai.tool_registry import build_tool_schemas, parse_tool_name, _build_meta_tools


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _FakeGenerator:
    """Minimal generator stub for testing tool schema building."""

    def __init__(self, gen_type: str, actions: list[str], available: bool = True):
        self._gen_type = gen_type
        self._actions = actions
        self._available = available

    @property
    def generator_type(self) -> str:
        return self._gen_type

    def get_available_actions(self) -> list[str]:
        return list(self._actions)

    def is_available(self) -> bool:
        return self._available

    def _action_test_action(self):
        """This is a test action docstring."""
        pass


@pytest.fixture
def mock_generators() -> dict[str, _FakeGenerator]:
    return {
        "mouse": _FakeGenerator("mouse", ["move_realistic", "click_left", "idle"]),
        "keyboard": _FakeGenerator("keyboard", ["type_text", "press_enter"]),
        "vscode": _FakeGenerator("vscode", ["launch", "open_file"]),
    }


# ---------------------------------------------------------------------------
# Tests: build_tool_schemas
# ---------------------------------------------------------------------------

class TestBuildToolSchemas:
    """Tests for build_tool_schemas()."""

    def test_generates_tools_for_all_actions(self, mock_generators):
        tools = build_tool_schemas(mock_generators)

        # 3 + 2 + 2 generator actions + 2 meta tools = 9
        assert len(tools) == 9

    def test_tool_names_use_double_underscore(self, mock_generators):
        tools = build_tool_schemas(mock_generators)

        gen_tools = [t for t in tools if not t["function"]["name"].startswith("meta__")]
        for tool in gen_tools:
            name = tool["function"]["name"]
            assert "__" in name, f"Tool name '{name}' missing '__' separator"

    def test_tool_format_is_openai_compatible(self, mock_generators):
        tools = build_tool_schemas(mock_generators)

        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"

    def test_skips_unavailable_generators(self):
        generators = {
            "available": _FakeGenerator("available", ["action1"], available=True),
            "unavailable": _FakeGenerator("unavailable", ["action2"], available=False),
        }
        tools = build_tool_schemas(generators)

        tool_names = [t["function"]["name"] for t in tools]
        assert "available__action1" in tool_names
        assert "unavailable__action2" not in tool_names

    def test_empty_generators_returns_only_meta_tools(self):
        tools = build_tool_schemas({})
        assert len(tools) == 2  # Only meta__idle and meta__think

    def test_known_actions_have_rich_descriptions(self, mock_generators):
        tools = build_tool_schemas(mock_generators)

        mouse_move = next(
            t for t in tools if t["function"]["name"] == "mouse__move_realistic"
        )
        desc = mouse_move["function"]["description"]
        assert "Bézier" in desc or "cursor" in desc.lower()

    def test_includes_meta_tools(self, mock_generators):
        tools = build_tool_schemas(mock_generators)

        tool_names = [t["function"]["name"] for t in tools]
        assert "meta__idle" in tool_names
        assert "meta__think" in tool_names


# ---------------------------------------------------------------------------
# Tests: _build_meta_tools
# ---------------------------------------------------------------------------

class TestMetaTools:
    """Tests for meta-tool definitions."""

    def test_idle_tool_has_duration_param(self):
        meta_tools = _build_meta_tools()
        idle = next(t for t in meta_tools if t["function"]["name"] == "meta__idle")

        params = idle["function"]["parameters"]
        assert "duration_seconds" in params["properties"]
        assert "duration_seconds" in params["required"]

    def test_think_tool_has_duration_param(self):
        meta_tools = _build_meta_tools()
        think = next(t for t in meta_tools if t["function"]["name"] == "meta__think")

        params = think["function"]["parameters"]
        assert "duration_seconds" in params["properties"]
        assert "duration_seconds" in params["required"]


# ---------------------------------------------------------------------------
# Tests: parse_tool_name
# ---------------------------------------------------------------------------

class TestParseToolName:
    """Tests for parse_tool_name()."""

    def test_parses_standard_name(self):
        gen_type, action = parse_tool_name("mouse__move_realistic")
        assert gen_type == "mouse"
        assert action == "move_realistic"

    def test_parses_meta_tool_name(self):
        gen_type, action = parse_tool_name("meta__idle")
        assert gen_type == "meta"
        assert action == "idle"

    def test_handles_action_with_underscores(self):
        gen_type, action = parse_tool_name("keyboard__press_hotkey_save")
        assert gen_type == "keyboard"
        assert action == "press_hotkey_save"

    def test_raises_on_missing_separator(self):
        with pytest.raises(ValueError, match="missing '__' separator"):
            parse_tool_name("invalid_name")

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            parse_tool_name("")
