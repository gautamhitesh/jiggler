"""Application interaction generator for the Developer Activity Simulator.

Handles window management, application launching, focus switching,
and window minimize/restore operations.
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import TYPE_CHECKING

import pyautogui

from simulator.generators.base import ActivityEvent, BaseGenerator

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig
    from simulator.logging.event_logger import EventLogger


class AppInteractionGenerator(BaseGenerator):
    """Generates application interaction events including window management.

    Uses pywinauto on Windows for reliable window control, with
    pyautogui as a cross-platform fallback.
    """

    ACTIONS = [
        "switch_app",
        "bring_to_foreground",
        "minimize_window",
        "restore_window",
        "focus_change",
        "alt_tab",
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pywinauto_available = False
        self._desktop = None

        # Try to import pywinauto on Windows
        if sys.platform == "win32":
            try:
                from pywinauto import Desktop

                self._desktop = Desktop(backend="uia")
                self._pywinauto_available = True
                self.logger.info("pywinauto available -- using native Windows window management")
            except ImportError:
                self.logger.warning("pywinauto not available -- falling back to pyautogui")

    @property
    def generator_type(self) -> str:
        return "app_interaction"

    def get_available_actions(self) -> list[str]:
        return list(self.ACTIONS)

    def is_available(self) -> bool:
        """App interaction is always available via pyautogui fallback."""
        return True

    def _execute_action(self, action_name: str) -> ActivityEvent:
        method = getattr(self, f"_action_{action_name}", None)
        if method is None:
            raise ValueError(f"Unknown app interaction action: {action_name}")
        return method()

    def _find_window(self, title_fragment: str):
        """Find a window by partial title match using pywinauto.

        Args:
            title_fragment: Partial window title to search for.

        Returns:
            Window wrapper if found, None otherwise.
        """
        if not self._pywinauto_available or self._desktop is None:
            return None

        try:
            windows = self._desktop.windows()
            for w in windows:
                try:
                    if title_fragment.lower() in w.window_text().lower():
                        return w
                except Exception:
                    continue
        except Exception as e:
            self.logger.debug("Window search failed: %s", e)

        return None

    def _action_bring_to_foreground(self) -> ActivityEvent:
        """Bring a target application window to the foreground."""
        app_name = self.rng.choice(self.config.target_applications)

        if self._pywinauto_available:
            window = self._find_window(app_name)
            if window:
                try:
                    window.set_focus()
                    return ActivityEvent(
                        event_type="app_focus",
                        action="bring_to_foreground",
                        application=app_name,
                        details={"method": "pywinauto", "window_title": window.window_text()},
                    )
                except Exception as e:
                    self.logger.debug("pywinauto focus failed, using Alt+Tab: %s", e)

        # Fallback: Alt+Tab
        pyautogui.hotkey("alt", "tab")
        time.sleep(0.5)

        return ActivityEvent(
            event_type="app_focus",
            action="bring_to_foreground",
            application=app_name,
            details={"method": "alt_tab_fallback"},
        )

    def _action_switch_app(self) -> ActivityEvent:
        """Switch between applications using Alt+Tab."""
        # Random number of Alt+Tab presses (1-3)
        tab_count = self.rng.randint(1, 3)

        pyautogui.hotkey("alt", "tab")
        time.sleep(0.3)

        for _ in range(tab_count - 1):
            pyautogui.press("tab")
            time.sleep(0.2)

        pyautogui.press("enter")
        time.sleep(0.3)

        return ActivityEvent(
            event_type="app_switch",
            action="switch_app",
            details={"tab_count": tab_count},
        )

    def _action_minimize_window(self) -> ActivityEvent:
        """Minimize the current foreground window."""
        if self._pywinauto_available and self._desktop:
            try:
                windows = self._desktop.windows()
                if windows:
                    active = windows[0]
                    title = active.window_text()
                    active.minimize()
                    return ActivityEvent(
                        event_type="window_manage",
                        action="minimize_window",
                        application=title,
                        details={"method": "pywinauto"},
                    )
            except Exception:
                pass

        # Fallback: Win+Down
        pyautogui.hotkey("win", "down")
        time.sleep(0.3)

        return ActivityEvent(
            event_type="window_manage",
            action="minimize_window",
            details={"method": "hotkey_fallback"},
        )

    def _action_restore_window(self) -> ActivityEvent:
        """Restore a minimized window."""
        if self._pywinauto_available and self._desktop:
            try:
                windows = self._desktop.windows()
                for w in windows:
                    try:
                        if w.is_minimized():
                            title = w.window_text()
                            w.restore()
                            return ActivityEvent(
                                event_type="window_manage",
                                action="restore_window",
                                application=title,
                                details={"method": "pywinauto"},
                            )
                    except Exception:
                        continue
            except Exception:
                pass

        # Fallback: Win+Up
        pyautogui.hotkey("win", "up")
        time.sleep(0.3)

        return ActivityEvent(
            event_type="window_manage",
            action="restore_window",
            details={"method": "hotkey_fallback"},
        )

    def _action_focus_change(self) -> ActivityEvent:
        """Click on a random area of the screen to simulate focus change."""
        screen_w, screen_h = pyautogui.size()

        # Click in a safe area (away from edges to avoid system UI)
        x = self.rng.randint(100, screen_w - 100)
        y = self.rng.randint(100, screen_h - 100)

        pyautogui.click(x, y)
        time.sleep(0.2)

        return ActivityEvent(
            event_type="focus_change",
            action="focus_change",
            details={"position": {"x": x, "y": y}},
        )

    def _action_alt_tab(self) -> ActivityEvent:
        """Simple Alt+Tab to switch to the next window."""
        pyautogui.hotkey("alt", "tab")
        time.sleep(0.5)

        return ActivityEvent(
            event_type="app_switch",
            action="alt_tab",
        )
