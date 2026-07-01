"""User Presence Detector — detects real human input to pause Jiggler.

Uses pynput background listeners to detect real mouse/keyboard activity
and signals the main loop to pause so the synthetic actions don't
interfere with the user's actual work.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig

logger = logging.getLogger(__name__)


class PresenceDetector:
    """Detects real user input and manages cooldown state.

    Runs pynput listeners in the background. When real input is detected,
    updates a timestamp. Jiggler's generators suppress this detector
    briefly while generating their own synthetic input to avoid self-detection.
    """

    def __init__(self, config: SimulatorConfig) -> None:
        """Initialize the presence detector.

        Args:
            config: Simulator configuration.
        """
        self._safety = config.safety
        self._last_user_input_time = 0.0
        self._suppress_detection = False
        self._suppress_lock = threading.Lock()
        
        self._mouse_listener = None
        self._keyboard_listener = None
        self._running = False

    def start(self) -> None:
        """Start the background input listeners."""
        if self._running:
            return

        try:
            from pynput import mouse, keyboard
        except ImportError:
            logger.warning("pynput not available — PresenceDetector disabled")
            return

        self._running = True

        def on_activity(*args, **kwargs) -> None:
            """Callback for any input activity."""
            with self._suppress_lock:
                if not self._suppress_detection:
                    self._last_user_input_time = time.monotonic()

        self._mouse_listener = mouse.Listener(
            on_move=on_activity,
            on_click=on_activity,
            on_scroll=on_activity,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=on_activity,
            on_release=on_activity,
        )

        self._mouse_listener.start()
        self._keyboard_listener.start()
        logger.info("PresenceDetector started background listeners")

    def stop(self) -> None:
        """Stop the background listeners."""
        self._running = False
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        logger.debug("PresenceDetector stopped listeners")

    def suppress(self) -> None:
        """Temporarily ignore input events (called by Jiggler generators)."""
        with self._suppress_lock:
            self._suppress_detection = True

    def unsuppress(self) -> None:
        """Resume listening to input events."""
        with self._suppress_lock:
            self._suppress_detection = False

    @property
    def seconds_since_last_input(self) -> float:
        """Seconds elapsed since the last detected user input."""
        return time.monotonic() - self._last_user_input_time

    @property
    def is_user_active(self) -> bool:
        """True if user input was detected within the cooldown window."""
        if not self._running:
            return False
        return self.seconds_since_last_input < self._safety.resume_delay_seconds

    def wait_for_user_idle(self, poll_interval: float = 0.5) -> None:
        """Block until the user has been idle for the full cooldown period."""
        if not self._running:
            return

        while self.is_user_active:
            time.sleep(poll_interval)
