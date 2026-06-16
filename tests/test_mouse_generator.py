"""Tests for the mouse generator module.

Uses mocking to avoid actual mouse movements during testing.
"""

from __future__ import annotations

import random
from unittest.mock import MagicMock, patch

import pytest

from simulator.config import SimulatorConfig
from simulator.generators.base import ActivityEvent
from simulator.generators.mouse import MouseGenerator


class TestMouseGenerator:
    """Tests for the MouseGenerator."""

    @pytest.fixture
    def config(self):
        return SimulatorConfig(mouse_enabled=True, random_seed=42)

    @pytest.fixture
    def event_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    @pytest.fixture
    def rng(self):
        return random.Random(42)

    @pytest.fixture
    def generator(self, config, event_logger, rng):
        gen = MouseGenerator(config, event_logger, rng)
        return gen

    def test_generator_type(self, generator):
        """Test generator type identifier."""
        assert generator.generator_type == "mouse"

    def test_available_actions(self, generator):
        """Test that all expected actions are available."""
        actions = generator.get_available_actions()
        assert "move_realistic" in actions
        assert "move_random" in actions
        assert "click_left" in actions
        assert "click_right" in actions
        assert "click_double" in actions
        assert "scroll_up" in actions
        assert "scroll_down" in actions
        assert "idle" in actions

    def test_dry_run_mode(self, generator):
        """Test that dry-run mode logs but doesn't execute."""
        generator.dry_run = True
        event = generator.execute("move_realistic")

        assert event.success is True
        assert event.details.get("dry_run") is True
        assert event.event_type == "mouse"

    def test_unknown_action_fails(self, generator):
        """Test that unknown actions are handled gracefully."""
        event = generator.execute("nonexistent_action")
        assert event.success is False
        assert "Unknown action" in event.error_message

    @patch("simulator.generators.mouse.pyautogui")
    def test_move_realistic(self, mock_pyautogui, generator):
        """Test realistic mouse movement."""
        mock_pyautogui.size.return_value = (1920, 1080)
        mock_pyautogui.position.return_value = (500, 500)
        mock_pyautogui.easeInOutQuad = lambda x: x
        mock_pyautogui.easeOutQuad = lambda x: x
        mock_pyautogui.easeInOutCubic = lambda x: x

        event = generator.execute("move_realistic")

        assert event.success is True
        mock_pyautogui.moveTo.assert_called_once()

    @patch("simulator.generators.mouse.pyautogui")
    def test_click_left(self, mock_pyautogui, generator):
        """Test left click action."""
        mock_pyautogui.position.return_value = (100, 100)

        event = generator.execute("click_left")

        assert event.success is True
        mock_pyautogui.click.assert_called_once()

    @patch("simulator.generators.mouse.pyautogui")
    def test_scroll_up(self, mock_pyautogui, generator):
        """Test scroll up action."""
        event = generator.execute("scroll_up")

        assert event.success is True
        mock_pyautogui.scroll.assert_called_once()
        # Scroll up should use positive clicks
        call_args = mock_pyautogui.scroll.call_args[0]
        assert call_args[0] > 0

    @patch("simulator.generators.mouse.pyautogui")
    def test_scroll_down(self, mock_pyautogui, generator):
        """Test scroll down action."""
        event = generator.execute("scroll_down")

        assert event.success is True
        mock_pyautogui.scroll.assert_called_once()
        # Scroll down should use negative clicks
        call_args = mock_pyautogui.scroll.call_args[0]
        assert call_args[0] < 0

    def test_pick_random_action(self, generator):
        """Test random action selection."""
        action = generator.pick_random_action()
        assert action in generator.get_available_actions()

    def test_event_logged(self, generator, event_logger):
        """Test that events are logged via the event logger."""
        generator.dry_run = True
        generator.execute("move_realistic")
        event_logger.log_event.assert_called_once()
