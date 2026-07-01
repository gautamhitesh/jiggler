"""Window Focus Guard — validates the foreground window before actions.

Ensures Jiggler only sends input events when a target application
is in the foreground, preventing accidental interaction with the
user's real work (email, chat, production terminals, etc.).
"""

from __future__ import annotations

import logging
import sys
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig

logger = logging.getLogger(__name__)


class WindowGuard:
    """Checks the foreground window belongs to the target allow-list.

    Before every action, generators call ``is_safe_to_act()`` to verify
    the current foreground window matches one of the configured
    ``target_applications``. If not, the guard can attempt to refocus
    a target app or block until one appears.
    """

    def __init__(self, config: SimulatorConfig) -> None:
        """Initialize the window guard.

        Args:
            config: Simulator configuration (uses target_applications
                    and safety settings).
        """
        self.config = config
        self._safety = config.safety
        self._target_apps = [app.lower() for app in config.target_applications]
        self._pywinauto_available = False
        self._desktop = None

        # Try to initialise pywinauto on Windows for reliable window ops
        if sys.platform == "win32":
            try:
                from pywinauto import Desktop
                self._desktop = Desktop(backend="uia")
                self._pywinauto_available = True
            except ImportError:
                logger.debug("pywinauto not available for WindowGuard")

        logger.info(
            "WindowGuard initialized — %d target app(s), refocus=%s",
            len(self._target_apps),
            self._safety.refocus_on_mismatch,
        )

    def get_foreground_window_title(self) -> str:
        """Get the title of the current foreground window.

        Returns:
            Window title string, or empty string on failure.
        """
        if sys.platform == "win32":
            return self._get_foreground_win32()
        else:
            return self._get_foreground_linux()

    def _get_foreground_win32(self) -> str:
        """Get foreground window title on Windows."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception as e:
            logger.debug("Failed to get foreground window (win32): %s", e)
            return ""

    def _get_foreground_linux(self) -> str:
        """Get foreground window title on Linux via xdotool."""
        try:
            import subprocess
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            logger.debug("Failed to get foreground window (linux): %s", e)
            return ""

    def is_safe_to_act(self) -> bool:
        """Check if the current foreground window is in the allow-list.

        Performs a case-insensitive substring match against each entry
        in ``config.target_applications``.

        Returns:
            True if the foreground window matches a target application.
        """
        title = self.get_foreground_window_title().lower()
        if not title:
            # Empty title — likely desktop or system process
            return False

        for target in self._target_apps:
            if target in title:
                return True

        if self._safety.log_blocked_actions:
            logger.debug(
                "WindowGuard: unsafe window '%s' does not match targets",
                title[:80],
            )
        return False

    def try_refocus_target(self) -> bool:
        """Attempt to bring a target application window to the foreground.

        Returns:
            True if a target window was found and focused.
        """
        if not self._safety.refocus_on_mismatch:
            return False

        if self._pywinauto_available and self._desktop:
            try:
                windows = self._desktop.windows()
                for w in windows:
                    try:
                        w_title = w.window_text().lower()
                        for target in self._target_apps:
                            if target in w_title:
                                w.set_focus()
                                time.sleep(0.5)  # Wait for focus settle
                                logger.info(
                                    "WindowGuard: refocused '%s'",
                                    w.window_text()[:60],
                                )
                                return True
                    except Exception:
                        continue
            except Exception as e:
                logger.debug("WindowGuard: refocus via pywinauto failed: %s", e)

        # Fallback: Alt+Tab (imprecise but better than nothing)
        try:
            import pyautogui
            pyautogui.hotkey("alt", "tab")
            time.sleep(0.5)
            if self.is_safe_to_act():
                logger.info("WindowGuard: refocused via Alt+Tab")
                return True
        except Exception:
            pass

        return False

    def wait_for_safe_window(self, timeout: Optional[float] = None) -> bool:
        """Block until a target application window is in the foreground.

        First attempts to refocus a target app. If that fails, polls
        every ``window_check_interval`` seconds until a target window
        appears or the timeout expires.

        Args:
            timeout: Maximum seconds to wait. Defaults to config value.

        Returns:
            True if a safe window was found, False on timeout.
        """
        if timeout is None:
            timeout = self._safety.window_guard_timeout

        # Try refocusing first
        if self.try_refocus_target() and self.is_safe_to_act():
            return True

        # Poll until safe or timeout
        start = time.monotonic()
        interval = self._safety.window_check_interval

        while (time.monotonic() - start) < timeout:
            if self.is_safe_to_act():
                return True
            time.sleep(interval)

        logger.warning(
            "WindowGuard: timed out after %.1fs waiting for target window",
            timeout,
        )
        return False
