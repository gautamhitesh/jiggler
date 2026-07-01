"""Tests for the User Presence Detector."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from simulator.config import SimulatorConfig
from simulator.safety.presence_detector import PresenceDetector


@pytest.fixture
def config():
    return SimulatorConfig().apply_overrides(
        safety={"resume_delay_seconds": 0.5, "presence_detection_enabled": True}
    )


class TestPresenceDetector:
    """Tests for the PresenceDetector."""

    @patch("pynput.keyboard")
    @patch("pynput.mouse")
    def test_start_and_stop(self, mock_mouse, mock_keyboard, config):
        detector = PresenceDetector(config)
        
        mock_mouse_listener = MagicMock()
        mock_keyboard_listener = MagicMock()
        mock_mouse.Listener.return_value = mock_mouse_listener
        mock_keyboard.Listener.return_value = mock_keyboard_listener
        
        detector.start()
        
        assert detector._running
        mock_mouse.Listener.assert_called_once()
        mock_keyboard.Listener.assert_called_once()
        mock_mouse_listener.start.assert_called_once()
        mock_keyboard_listener.start.assert_called_once()
        
        detector.stop()
        
        assert not detector._running
        mock_mouse_listener.stop.assert_called_once()
        mock_keyboard_listener.stop.assert_called_once()

    def test_suppression_logic(self, config):
        detector = PresenceDetector(config)
        assert not detector._suppress_detection
        
        detector.suppress()
        assert detector._suppress_detection
        
        detector.unsuppress()
        assert not detector._suppress_detection

    def test_user_active_state(self, config):
        detector = PresenceDetector(config)
        detector._running = True
        
        # Manually trigger input
        detector._last_user_input_time = time.monotonic()
        
        # User should be active
        assert detector.is_user_active
        
        # Wait for cooldown
        time.sleep(0.6)
        
        # User should be inactive
        assert not detector.is_user_active
