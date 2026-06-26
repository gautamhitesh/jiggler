"""Tests for pyautogui FailSafeException handling and graceful termination."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from pyautogui import FailSafeException

from simulator.config import SimulatorConfig
from simulator.controller import Controller
from simulator.scenarios.base import BaseScenario
from simulator.scheduler import ScheduledAction


class TestFailSafeHandling:
    """Verify that FailSafeException propagates correctly and is handled gracefully."""

    def test_failsafe_exception_graceful_shutdown(self):
        """Test that a FailSafeException raised in a generator triggers a clean shutdown."""
        # 1. Setup config (very short, minimal features enabled)
        config = SimulatorConfig(
            duration_minutes=1,
            mouse_enabled=True,
            keyboard_enabled=False,
            vscode_enabled=False,
            random_seed=42,
        )

        # 2. Initialize controller
        controller = Controller(config, dry_run=False)

        # Mock the scenario to yield a single mouse click action
        mock_scenario_cls = MagicMock()
        mock_scenario = MagicMock(spec=BaseScenario)
        mock_scenario.name = "Mock Scenario"
        mock_scenario.description = "Mock description"
        mock_scenario.get_action_sequence.return_value = [
            ScheduledAction(delay=0.1, generator_type="mouse", action_name="click_left")
        ]
        mock_scenario_cls.return_value = mock_scenario

        # Replace SCENARIO_MAP temporarily
        with patch.dict(Controller.SCENARIO_MAP, {config.scenario: mock_scenario_cls}):
            # Mock the MouseGenerator._execute_action to raise FailSafeException
            mouse_generator = controller.generators["mouse"]
            mouse_generator._execute_action = MagicMock(side_effect=FailSafeException)

            # Mock loggers and reporters to avoid actual file system writes or clean them up
            controller.event_logger.log_event = MagicMock()
            controller.event_logger.log_session_start = MagicMock()
            controller.event_logger.log_session_end = MagicMock()
            controller.event_logger.close = MagicMock()
            controller.reporter.generate_reports = MagicMock()

            # 3. Run controller
            controller.run()

            # 4. Assertions
            # Verify the exception was raised and caught
            mouse_generator._execute_action.assert_called_once_with("click_left")
            
            # The session end reason should be "interrupted"
            controller.event_logger.log_session_end.assert_called_once_with("interrupted")
            
            # Reports should still be generated
            controller.reporter.generate_reports.assert_called_once()
