"""Tool registry — maps activity generators to OpenAI-compatible tool schemas.

Introspects existing generators to auto-build tool definitions that the
LLM can call, plus meta-tools for idle/thinking pauses.
"""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from simulator.generators.base import BaseGenerator

logger = logging.getLogger(__name__)

# Default descriptions for well-known generator actions.
# Falls back to method docstring or a generic description.
_ACTION_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "mouse": {
        "move_realistic": "Move the mouse cursor along a realistic curved Bézier path to a random screen position.",
        "move_random": "Instantly teleport the mouse cursor to a random screen position.",
        "click_left": "Perform a left mouse click at the current cursor position.",
        "click_right": "Perform a right mouse click at the current cursor position.",
        "click_double": "Perform a double mouse click at the current cursor position.",
        "scroll_up": "Scroll the mouse wheel upward by a random amount.",
        "scroll_down": "Scroll the mouse wheel downward by a random amount.",
        "idle": "Keep the mouse stationary for a short random duration (simulates reading).",
    },
    "keyboard": {
        "type_text": "Type a short text sample with realistic typing speed and rhythm.",
        "type_code_snippet": "Type a realistic code snippet (Python, JavaScript, YAML, etc.) with natural cadence.",
        "press_key": "Press a single random key (arrow keys, space, enter, tab, etc.).",
        "press_hotkey_save": "Press Ctrl+S to save the current file.",
        "press_hotkey_copy": "Press Ctrl+C to copy selected text.",
        "press_hotkey_paste": "Press Ctrl+V to paste from clipboard.",
        "press_hotkey_undo": "Press Ctrl+Z to undo the last action.",
        "press_enter": "Press the Enter key.",
        "press_tab": "Press the Tab key for indentation.",
        "press_backspace": "Press Backspace to delete a character.",
    },
    "vscode": {
        "launch": "Launch VS Code with the test workspace folder.",
        "open_file": "Open a file in VS Code using Quick Open (Ctrl+P).",
        "create_new_file": "Create a new untitled file in VS Code (Ctrl+N).",
        "switch_tab": "Switch between open editor tabs in VS Code.",
        "scroll_down": "Scroll down in the current VS Code editor.",
        "scroll_up": "Scroll up in the current VS Code editor.",
        "save_file": "Save the currently active file in VS Code (Ctrl+S).",
        "toggle_terminal": "Toggle the integrated terminal in VS Code (Ctrl+`).",
        "go_to_line": "Go to a random line number in VS Code (Ctrl+G).",
        "find_text": "Open the Find dialog and search for a code pattern.",
        "close_tab": "Close the current editor tab in VS Code (Ctrl+W).",
    },
    "app_interaction": {
        "switch_app": "Switch between applications using Alt+Tab.",
        "bring_to_foreground": "Bring a target application window to the foreground.",
        "minimize_window": "Minimize the current foreground window.",
        "restore_window": "Restore a previously minimized window.",
        "focus_change": "Click on a random screen area to simulate focus change.",
        "alt_tab": "Simple Alt+Tab to switch to the next window.",
    },
}


def build_tool_schemas(
    generators: dict[str, BaseGenerator],
) -> list[dict[str, Any]]:
    """Build OpenAI-compatible tool definitions from registered generators.

    Each generator action becomes a callable tool with the naming convention
    ``{generator_type}__{action_name}`` (double underscore separator).

    Args:
        generators: Map of generator_type → generator instance.

    Returns:
        List of tool definition dicts in OpenAI function-calling format.
    """
    tools: list[dict[str, Any]] = []

    for gen_type, generator in generators.items():
        if not generator.is_available():
            logger.debug("Skipping unavailable generator: %s", gen_type)
            continue

        for action_name in generator.get_available_actions():
            tool_name = f"{gen_type}__{action_name}"
            description = _get_action_description(generator, gen_type, action_name)

            tools.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            })

    # Add meta-tools
    tools.extend(_build_meta_tools())

    logger.info("Built %d tool definitions from %d generators", len(tools), len(generators))
    return tools


def _get_action_description(
    generator: BaseGenerator,
    gen_type: str,
    action_name: str,
) -> str:
    """Get a human-readable description for a generator action.

    Priority: hardcoded descriptions → method docstring → fallback.

    Args:
        generator: The generator instance.
        gen_type: Generator type identifier.
        action_name: Action name.

    Returns:
        Description string.
    """
    # Check hardcoded descriptions first
    if gen_type in _ACTION_DESCRIPTIONS and action_name in _ACTION_DESCRIPTIONS[gen_type]:
        return _ACTION_DESCRIPTIONS[gen_type][action_name]

    # Try to extract docstring from the _action_* method
    method = getattr(generator, f"_action_{action_name}", None)
    if method is not None:
        doc = inspect.getdoc(method)
        if doc:
            return doc.split("\n")[0]  # First line only

    # Fallback
    return f"Execute {gen_type} action: {action_name}"


def _build_meta_tools() -> list[dict[str, Any]]:
    """Build meta-tools for idle pauses and thinking time.

    Returns:
        List of meta-tool definitions.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "meta__idle",
                "description": (
                    "Take a short break — stop all activity for a brief period. "
                    "Use this to simulate natural human idle time like reading, "
                    "thinking, or taking a sip of coffee."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration_seconds": {
                            "type": "number",
                            "description": "How many seconds to stay idle (1-30).",
                            "minimum": 1,
                            "maximum": 30,
                        }
                    },
                    "required": ["duration_seconds"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "meta__think",
                "description": (
                    "Pause briefly to 'think' before the next action — "
                    "simulates a developer contemplating what to do next. "
                    "Shorter than idle; represents a momentary pause."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration_seconds": {
                            "type": "number",
                            "description": "How many seconds to pause (0.5-5).",
                            "minimum": 0.5,
                            "maximum": 5,
                        }
                    },
                    "required": ["duration_seconds"],
                },
            },
        },
    ]


def parse_tool_name(tool_name: str) -> tuple[str, str]:
    """Parse a tool name back into generator_type and action_name.

    Args:
        tool_name: Tool name in ``generator__action`` format.

    Returns:
        Tuple of (generator_type, action_name).

    Raises:
        ValueError: If the tool name doesn't contain the ``__`` separator.
    """
    if "__" not in tool_name:
        raise ValueError(f"Invalid tool name format (missing '__' separator): {tool_name}")

    parts = tool_name.split("__", 1)
    return parts[0], parts[1]
