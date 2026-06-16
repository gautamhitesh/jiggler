"""Tests for the keyboard generator module.

Uses mocking to avoid actual keyboard input during testing.
"""

from __future__ import annotations

import random
from unittest.mock import MagicMock, patch

import pytest

from simulator.config import SimulatorConfig
from simulator.generators.keyboard import (
    CODE_SNIPPETS,
    TEXT_SAMPLES,
    KeyboardGenerator,
)


class TestKeyboardGenerator:
    """Tests for the KeyboardGenerator."""

    @pytest.fixture
    def config(self):
        return SimulatorConfig(
            keyboard_enabled=True,
            typing_speed_wpm=60,
            random_seed=42,
        )

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
        return KeyboardGenerator(config, event_logger, rng)

    def test_generator_type(self, generator):
        """Test generator type identifier."""
        assert generator.generator_type == "keyboard"

    def test_available_actions(self, generator):
        """Test that all expected actions are available."""
        actions = generator.get_available_actions()
        assert "type_text" in actions
        assert "type_code_snippet" in actions
        assert "press_key" in actions
        assert "press_hotkey_save" in actions
        assert "press_enter" in actions

    def test_dry_run_mode(self, generator):
        """Test that dry-run mode works correctly."""
        generator.dry_run = True
        event = generator.execute("type_text")
        assert event.success is True
        assert event.details.get("dry_run") is True

    def test_key_delay_calculation(self, generator):
        """Test that key delay is calculated from WPM."""
        delay = generator._calculate_key_delay()
        # At 60 WPM: 60 chars/s => 360 chars/min => ~0.167s per char
        # With Gaussian variation, should be in a reasonable range
        assert 0.02 <= delay <= 1.0  # Between floor and reasonable max

    def test_key_delay_varies(self, generator):
        """Test that key delays are not all identical (Gaussian variation)."""
        delays = [generator._calculate_key_delay() for _ in range(20)]
        unique_delays = set(delays)
        assert len(unique_delays) > 1, "Delays should vary due to Gaussian distribution"

    @patch("simulator.generators.keyboard.pyautogui")
    @patch("simulator.generators.keyboard.time")
    def test_type_text(self, mock_time, mock_pyautogui, generator):
        """Test text typing action."""
        mock_time.sleep = MagicMock()

        event = generator.execute("type_text")

        assert event.success is True
        assert event.event_type == "keyboard_type"
        assert "text_length" in event.details

    @patch("simulator.generators.keyboard.pyautogui")
    @patch("simulator.generators.keyboard.time")
    def test_type_code_snippet(self, mock_time, mock_pyautogui, generator):
        """Test code snippet typing action."""
        mock_time.sleep = MagicMock()

        event = generator.execute("type_code_snippet")

        assert event.success is True
        assert event.event_type == "keyboard_type"
        assert "snippet" in event.details
        assert event.details["snippet"] in CODE_SNIPPETS

    @patch("simulator.generators.keyboard.pyautogui")
    def test_press_hotkey_save(self, mock_pyautogui, generator):
        """Test Ctrl+S hotkey action."""
        event = generator.execute("press_hotkey_save")

        assert event.success is True
        assert event.event_type == "keyboard_hotkey"
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "s")

    @patch("simulator.generators.keyboard.pyautogui")
    def test_press_hotkey_copy(self, mock_pyautogui, generator):
        """Test Ctrl+C hotkey action."""
        event = generator.execute("press_hotkey_copy")

        assert event.success is True
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "c")

    def test_code_snippets_exist(self):
        """Test that code snippet library is populated."""
        assert len(CODE_SNIPPETS) > 0
        assert "python_function" in CODE_SNIPPETS
        assert "javascript_module" in CODE_SNIPPETS

    def test_text_samples_exist(self):
        """Test that text sample library is populated."""
        assert len(TEXT_SAMPLES) > 0
        for sample in TEXT_SAMPLES:
            assert len(sample) > 0
