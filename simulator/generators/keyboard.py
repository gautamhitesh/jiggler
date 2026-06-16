"""Keyboard activity generator for the Developer Activity Simulator.

Generates keyboard events including text typing, code snippets,
single key presses, and hotkey combinations.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

import pyautogui

from simulator.generators.base import ActivityEvent, BaseGenerator

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig
    from simulator.logging.event_logger import EventLogger


# Built-in code snippet templates for realistic typing simulation
CODE_SNIPPETS = {
    "python_function": '''def calculate_metrics(data: list[dict]) -> dict:
    """Calculate aggregate metrics from raw data entries."""
    total = sum(entry.get("value", 0) for entry in data)
    count = len(data)
    average = total / count if count > 0 else 0
    return {"total": total, "count": count, "average": round(average, 2)}
''',
    "python_class": '''class DataProcessor:
    """Processes and transforms raw data for analysis."""

    def __init__(self, source: str, batch_size: int = 100):
        self.source = source
        self.batch_size = batch_size
        self._cache = {}

    def process(self, raw_data: list) -> list:
        results = []
        for i in range(0, len(raw_data), self.batch_size):
            batch = raw_data[i:i + self.batch_size]
            results.extend(self._transform(batch))
        return results

    def _transform(self, batch: list) -> list:
        return [item.strip().lower() for item in batch if item]
''',
    "javascript_module": '''export class EventEmitter {
    constructor() {
        this.listeners = new Map();
    }

    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
        return this;
    }

    emit(event, ...args) {
        const handlers = this.listeners.get(event) || [];
        handlers.forEach(handler => handler(...args));
    }
}
''',
    "markdown_paragraph": '''## Project Status Update

The development team has completed the initial implementation of the
core simulation engine. Key milestones achieved this sprint include:

- Modular generator architecture with plugin support
- Configurable scheduling engine with multiple scenario profiles
- Structured event logging with JSON Lines format
- Comprehensive reporting with JSON, CSV, and HTML output

Next steps involve integration testing and performance optimization
to ensure the tool meets the specified resource constraints.
''',
    "python_test": '''import pytest

class TestCalculator:
    """Test suite for the calculator module."""

    def test_addition(self):
        assert calculate(2, 3, "add") == 5

    def test_division_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            calculate(10, 0, "divide")

    @pytest.mark.parametrize("a, b, expected", [
        (1, 1, 2),
        (0, 0, 0),
        (-1, 1, 0),
    ])
    def test_parametrized_add(self, a, b, expected):
        assert calculate(a, b, "add") == expected
''',
    "config_yaml": '''# Application Configuration
server:
  host: "0.0.0.0"
  port: 8080
  workers: 4
  debug: false

database:
  url: "postgresql://localhost:5432/app_db"
  pool_size: 20
  timeout: 30

logging:
  level: "INFO"
  format: "%(asctime)s [%(levelname)s] %(message)s"
''',
}

# Short text samples for quick typing bursts
TEXT_SAMPLES = [
    "The quick brown fox jumps over the lazy dog.",
    "Hello, world! This is a test of the keyboard simulation.",
    "import os\nimport sys\nfrom pathlib import Path",
    "TODO: Refactor this function to improve performance.",
    "# Fix: Handle edge case when input is empty",
    "console.log('Debug:', JSON.stringify(data, null, 2));",
    "SELECT * FROM users WHERE active = true ORDER BY created_at DESC;",
    "def main():\n    print('Starting application...')\n",
]


class KeyboardGenerator(BaseGenerator):
    """Generates keyboard activity including text typing, code snippets, and hotkeys.

    Simulates realistic typing with configurable speed and natural
    inter-key delays using a Gaussian distribution around the target WPM.
    """

    ACTIONS = [
        "type_text",
        "type_code_snippet",
        "press_key",
        "press_hotkey_save",
        "press_hotkey_copy",
        "press_hotkey_paste",
        "press_hotkey_undo",
        "press_enter",
        "press_tab",
        "press_backspace",
    ]

    @property
    def generator_type(self) -> str:
        return "keyboard"

    def get_available_actions(self) -> list[str]:
        return list(self.ACTIONS)

    def _execute_action(self, action_name: str) -> ActivityEvent:
        """Execute a keyboard action.

        Args:
            action_name: One of the supported keyboard actions.

        Returns:
            ActivityEvent describing the keyboard action.
        """
        method = getattr(self, f"_action_{action_name}", None)
        if method is None:
            raise ValueError(f"Unknown keyboard action: {action_name}")
        return method()

    def _calculate_key_delay(self) -> float:
        """Calculate delay between keystrokes based on configured WPM.

        Uses a Gaussian distribution around the target delay for
        natural-feeling typing rhythm.

        Returns:
            Delay in seconds between keystrokes.
        """
        # Average word length is 5 characters + 1 space = 6 chars per word
        chars_per_minute = self.config.typing_speed_wpm * 6
        base_delay = 60.0 / chars_per_minute  # seconds per character

        # Add natural variation (±30%)
        delay = self.rng.gauss(base_delay, base_delay * 0.3)
        return max(0.02, delay)  # Floor at 20ms

    def _type_with_delays(self, text: str) -> float:
        """Type text character by character with realistic delays.

        Args:
            text: The text to type.

        Returns:
            Total time spent typing in seconds.
        """
        total_time = 0.0
        for char in text:
            delay = self._calculate_key_delay()

            # Longer pauses at line breaks and punctuation
            if char == "\n":
                delay *= 3
            elif char in ".!?;:":
                delay *= 2

            time.sleep(delay)
            pyautogui.write(char) if char != "\n" else pyautogui.press("enter")
            total_time += delay

        return total_time

    def _action_type_text(self) -> ActivityEvent:
        """Type a random short text sample."""
        text = self.rng.choice(TEXT_SAMPLES)
        duration = self._type_with_delays(text)

        return ActivityEvent(
            event_type="keyboard_type",
            action="type_text",
            details={
                "text_length": len(text),
                "duration_seconds": round(duration, 2),
                "preview": text[:50] + ("..." if len(text) > 50 else ""),
            },
        )

    def _action_type_code_snippet(self) -> ActivityEvent:
        """Type a random code snippet from the built-in library."""
        snippet_name = self.rng.choice(list(CODE_SNIPPETS.keys()))
        snippet = CODE_SNIPPETS[snippet_name]
        duration = self._type_with_delays(snippet)

        return ActivityEvent(
            event_type="keyboard_type",
            action="type_code_snippet",
            details={
                "snippet": snippet_name,
                "text_length": len(snippet),
                "duration_seconds": round(duration, 2),
            },
        )

    def _action_press_key(self) -> ActivityEvent:
        """Press a random single key."""
        keys = ["space", "enter", "tab", "backspace", "delete", "escape",
                "up", "down", "left", "right", "home", "end"]
        key = self.rng.choice(keys)
        pyautogui.press(key)

        return ActivityEvent(
            event_type="keyboard_press",
            action="press_key",
            details={"key": key},
        )

    def _action_press_hotkey_save(self) -> ActivityEvent:
        """Press Ctrl+S to save."""
        pyautogui.hotkey("ctrl", "s")
        return ActivityEvent(
            event_type="keyboard_hotkey",
            action="press_hotkey_save",
            details={"hotkey": "ctrl+s"},
        )

    def _action_press_hotkey_copy(self) -> ActivityEvent:
        """Press Ctrl+C to copy."""
        pyautogui.hotkey("ctrl", "c")
        return ActivityEvent(
            event_type="keyboard_hotkey",
            action="press_hotkey_copy",
            details={"hotkey": "ctrl+c"},
        )

    def _action_press_hotkey_paste(self) -> ActivityEvent:
        """Press Ctrl+V to paste."""
        pyautogui.hotkey("ctrl", "v")
        return ActivityEvent(
            event_type="keyboard_hotkey",
            action="press_hotkey_paste",
            details={"hotkey": "ctrl+v"},
        )

    def _action_press_hotkey_undo(self) -> ActivityEvent:
        """Press Ctrl+Z to undo."""
        pyautogui.hotkey("ctrl", "z")
        return ActivityEvent(
            event_type="keyboard_hotkey",
            action="press_hotkey_undo",
            details={"hotkey": "ctrl+z"},
        )

    def _action_press_enter(self) -> ActivityEvent:
        """Press Enter key."""
        pyautogui.press("enter")
        return ActivityEvent(
            event_type="keyboard_press",
            action="press_enter",
            details={"key": "enter"},
        )

    def _action_press_tab(self) -> ActivityEvent:
        """Press Tab key."""
        pyautogui.press("tab")
        return ActivityEvent(
            event_type="keyboard_press",
            action="press_tab",
            details={"key": "tab"},
        )

    def _action_press_backspace(self) -> ActivityEvent:
        """Press Backspace key."""
        pyautogui.press("backspace")
        return ActivityEvent(
            event_type="keyboard_press",
            action="press_backspace",
            details={"key": "backspace"},
        )
