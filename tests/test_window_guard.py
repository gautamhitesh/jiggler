"""Tests for the Window Focus Guard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from simulator.config import SimulatorConfig
from simulator.safety.window_guard import WindowGuard


@pytest.fixture
def config():
    return SimulatorConfig().apply_overrides(
        target_applications=["Visual Studio Code", "Terminal"],
        safety={"window_guard_timeout": 0.5, "window_check_interval": 0.1, "refocus_on_mismatch": True}
    )


class TestWindowGuard:
    """Tests for the WindowGuard."""

    def test_is_safe_to_act_with_target(self, config):
        guard = WindowGuard(config)
        
        with patch.object(guard, "get_foreground_window_title", return_value="my_project - Visual Studio Code"):
            assert guard.is_safe_to_act()
            
    def test_is_safe_to_act_case_insensitive(self, config):
        guard = WindowGuard(config)
        
        with patch.object(guard, "get_foreground_window_title", return_value="visual STUDIO code"):
            assert guard.is_safe_to_act()

    def test_is_safe_to_act_with_non_target(self, config):
        guard = WindowGuard(config)
        
        with patch.object(guard, "get_foreground_window_title", return_value="Google Chrome"):
            assert not guard.is_safe_to_act()

    def test_is_safe_to_act_with_empty_title(self, config):
        guard = WindowGuard(config)
        
        with patch.object(guard, "get_foreground_window_title", return_value=""):
            assert not guard.is_safe_to_act()

    @patch("time.sleep")
    def test_wait_for_safe_window_success(self, mock_sleep, config):
        guard = WindowGuard(config)
        guard.try_refocus_target = MagicMock(return_value=False)
        
        # Returns false twice, then true
        guard.get_foreground_window_title = MagicMock(side_effect=[
            "Spotify",
            "Slack",
            "Terminal"
        ])
        
        result = guard.wait_for_safe_window(timeout=1.0)
        
        assert result is True
        assert guard.get_foreground_window_title.call_count == 3
        
    def test_wait_for_safe_window_timeout(self, config):
        guard = WindowGuard(config)
        guard.try_refocus_target = MagicMock(return_value=False)
        guard.get_foreground_window_title = MagicMock(return_value="Discord")
        
        result = guard.wait_for_safe_window(timeout=0.2)
        
        assert result is False
