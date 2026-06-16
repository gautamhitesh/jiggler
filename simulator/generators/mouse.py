"""Mouse activity generator for the Developer Activity Simulator.

Generates realistic mouse movements, clicks, and idle periods
using pyautogui for cross-platform support.
"""

from __future__ import annotations

import math
import random
import time
from typing import TYPE_CHECKING

import pyautogui

from simulator.generators.base import ActivityEvent, BaseGenerator

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig
    from simulator.logging.event_logger import EventLogger

# Disable pyautogui fail-safe for long-running tests
# The controller handles graceful shutdown via signal handlers
pyautogui.FAILSAFE = True  # Keep failsafe on — move mouse to corner to abort
pyautogui.PAUSE = 0.05  # Minimal pause between pyautogui calls


class MouseGenerator(BaseGenerator):
    """Generates mouse activity including realistic movements, clicks, and idle periods.

    Uses Bézier curve interpolation for natural-looking mouse paths
    and supports configurable movement frequency.
    """

    ACTIONS = [
        "move_realistic",
        "move_random",
        "click_left",
        "click_right",
        "click_double",
        "scroll_up",
        "scroll_down",
        "idle",
    ]

    @property
    def generator_type(self) -> str:
        return "mouse"

    def get_available_actions(self) -> list[str]:
        return list(self.ACTIONS)

    def _execute_action(self, action_name: str) -> ActivityEvent:
        """Execute a mouse action.

        Args:
            action_name: One of the supported mouse actions.

        Returns:
            ActivityEvent describing the mouse action.
        """
        method = getattr(self, f"_action_{action_name}", None)
        if method is None:
            raise ValueError(f"Unknown mouse action: {action_name}")
        return method()

    def _action_move_realistic(self) -> ActivityEvent:
        """Move cursor along a realistic Bézier curve path to a random target."""
        screen_w, screen_h = pyautogui.size()
        target_x = self.rng.randint(50, screen_w - 50)
        target_y = self.rng.randint(50, screen_h - 50)

        # Calculate duration based on distance for natural speed
        current_x, current_y = pyautogui.position()
        distance = math.sqrt((target_x - current_x) ** 2 + (target_y - current_y) ** 2)
        duration = max(0.2, min(2.0, distance / 1000.0))

        # Use pyautogui's built-in tweening for smooth movement
        tween = self.rng.choice([
            pyautogui.easeInOutQuad,
            pyautogui.easeOutQuad,
            pyautogui.easeInOutCubic,
        ])

        pyautogui.moveTo(target_x, target_y, duration=duration, tween=tween)

        return ActivityEvent(
            event_type="mouse_move",
            action="move_realistic",
            details={
                "from": {"x": current_x, "y": current_y},
                "to": {"x": target_x, "y": target_y},
                "duration": round(duration, 3),
            },
        )

    def _action_move_random(self) -> ActivityEvent:
        """Move cursor instantly to a random screen position."""
        screen_w, screen_h = pyautogui.size()
        target_x = self.rng.randint(0, screen_w - 1)
        target_y = self.rng.randint(0, screen_h - 1)

        pyautogui.moveTo(target_x, target_y, duration=0.1)

        return ActivityEvent(
            event_type="mouse_move",
            action="move_random",
            details={"to": {"x": target_x, "y": target_y}},
        )

    def _action_click_left(self) -> ActivityEvent:
        """Perform a left click at the current cursor position."""
        x, y = pyautogui.position()
        pyautogui.click()

        return ActivityEvent(
            event_type="mouse_click",
            action="click_left",
            details={"position": {"x": x, "y": y}, "button": "left"},
        )

    def _action_click_right(self) -> ActivityEvent:
        """Perform a right click at the current cursor position."""
        x, y = pyautogui.position()
        pyautogui.rightClick()

        return ActivityEvent(
            event_type="mouse_click",
            action="click_right",
            details={"position": {"x": x, "y": y}, "button": "right"},
        )

    def _action_click_double(self) -> ActivityEvent:
        """Perform a double click at the current cursor position."""
        x, y = pyautogui.position()
        pyautogui.doubleClick()

        return ActivityEvent(
            event_type="mouse_click",
            action="click_double",
            details={"position": {"x": x, "y": y}, "button": "double"},
        )

    def _action_scroll_up(self) -> ActivityEvent:
        """Scroll up by a random number of clicks."""
        clicks = self.rng.randint(1, 5)
        pyautogui.scroll(clicks)

        return ActivityEvent(
            event_type="mouse_scroll",
            action="scroll_up",
            details={"clicks": clicks, "direction": "up"},
        )

    def _action_scroll_down(self) -> ActivityEvent:
        """Scroll down by a random number of clicks."""
        clicks = self.rng.randint(1, 5)
        pyautogui.scroll(-clicks)

        return ActivityEvent(
            event_type="mouse_scroll",
            action="scroll_down",
            details={"clicks": clicks, "direction": "down"},
        )

    def _action_idle(self) -> ActivityEvent:
        """Stay idle for a short random duration."""
        duration = self.rng.uniform(1.0, 5.0)
        time.sleep(duration)

        return ActivityEvent(
            event_type="mouse_idle",
            action="idle",
            details={"duration_seconds": round(duration, 2)},
        )
