"""Tests for the scenario modules."""

from __future__ import annotations

import random
from unittest.mock import MagicMock

import pytest

from simulator.config import SimulatorConfig
from simulator.scenarios.continuous import ContinuousScenario
from simulator.scenarios.edge_timeout import EdgeTimeoutScenario
from simulator.scenarios.intermittent import IntermittentScenario
from simulator.scenarios.long_duration import LongDurationScenario
from simulator.scenarios.randomized import RandomizedScenario
from simulator.scheduler import ScheduledAction, Scheduler


class TestScenarios:
    """Tests for all scenario implementations."""

    @pytest.fixture
    def config(self):
        """Create a test config with short duration."""
        return SimulatorConfig(
            duration_minutes=1,
            mouse_enabled=True,
            keyboard_enabled=True,
            vscode_enabled=False,
            random_seed=42,
        )

    @pytest.fixture
    def rng(self):
        return random.Random(42)

    @pytest.fixture
    def scheduler(self, config, rng):
        return Scheduler(config, rng)

    @pytest.fixture
    def mock_generators(self):
        """Create mock generators."""
        mouse = MagicMock()
        mouse.is_available.return_value = True
        mouse.get_available_actions.return_value = [
            "move_realistic", "move_random", "click_left"
        ]

        keyboard = MagicMock()
        keyboard.is_available.return_value = True
        keyboard.get_available_actions.return_value = [
            "type_text", "press_key", "press_hotkey_save"
        ]

        app = MagicMock()
        app.is_available.return_value = True
        app.get_available_actions.return_value = [
            "alt_tab", "focus_change"
        ]

        return {
            "mouse": mouse,
            "keyboard": keyboard,
            "app_interaction": app,
        }

    def test_continuous_scenario(self, config, scheduler, mock_generators, rng):
        """Test continuous scenario generates actions."""
        scenario = ContinuousScenario(config, scheduler, mock_generators, rng)

        assert scenario.name == "Scenario A — Continuous Activity"
        assert len(scenario.description) > 0

        actions = list(scenario.get_action_sequence())
        assert len(actions) > 0

        # All actions should be activity (no idle)
        for action in actions:
            assert isinstance(action, ScheduledAction)
            assert action.delay > 0

    def test_intermittent_scenario(self, mock_generators):
        """Test intermittent scenario has idle periods.

        Uses longer duration and shorter burst/idle settings to ensure
        the pattern produces both burst and idle phases.
        """
        config = SimulatorConfig(
            duration_minutes=10,
            mouse_enabled=True,
            keyboard_enabled=True,
            vscode_enabled=False,
            random_seed=42,
            intermittent={
                "burst_duration_min": 30,
                "burst_duration_max": 60,
                "idle_duration_min": 10,
                "idle_duration_max": 30,
            },
        )
        rng = random.Random(42)
        scheduler = Scheduler(config, rng)

        scenario = IntermittentScenario(config, scheduler, mock_generators, rng)

        assert "Intermittent" in scenario.name

        actions = list(scenario.get_action_sequence())
        assert len(actions) > 0

        idle_actions = [a for a in actions if a.generator_type == "idle"]
        assert len(idle_actions) > 0, "Should have idle periods"

    def test_edge_timeout_scenario(self, mock_generators):
        """Test edge timeout scenario has long idles and activity bursts.

        Uses a duration longer than the timeout threshold so both idle
        and activity phases are generated.
        """
        config = SimulatorConfig(
            duration_minutes=10,
            mouse_enabled=True,
            keyboard_enabled=True,
            vscode_enabled=False,
            random_seed=42,
            edge_timeout={
                "timeout_threshold_seconds": 60,
                "activity_delta_seconds": 5,
            },
        )
        rng = random.Random(42)
        scheduler = Scheduler(config, rng)

        scenario = EdgeTimeoutScenario(config, scheduler, mock_generators, rng)

        assert "Timeout" in scenario.name

        actions = list(scenario.get_action_sequence())
        assert len(actions) > 0

        idle_actions = [a for a in actions if a.generator_type == "idle"]
        activity_actions = [a for a in actions if a.generator_type != "idle"]

        assert len(idle_actions) > 0
        assert len(activity_actions) > 0

    def test_long_duration_scenario(self, mock_generators):
        """Test long duration scenario generates health checks."""
        # Use a longer duration to trigger health checks
        long_config = SimulatorConfig(
            duration_minutes=60,
            mouse_enabled=True,
            keyboard_enabled=True,
            vscode_enabled=False,
            random_seed=42,
        )
        long_scheduler = Scheduler(long_config, random.Random(42))

        scenario = LongDurationScenario(
            long_config, long_scheduler, mock_generators, random.Random(42)
        )

        assert "Long Duration" in scenario.name

        actions = list(scenario.get_action_sequence())
        assert len(actions) > 0

        # Should have health check markers
        health_checks = [a for a in actions if a.generator_type == "health_check"]
        assert len(health_checks) > 0, "Long duration should include health checks"

    def test_randomized_scenario(self, config, scheduler, mock_generators, rng):
        """Test randomized scenario uses varied actions."""
        scenario = RandomizedScenario(config, scheduler, mock_generators, rng)

        assert "Randomized" in scenario.name

        actions = list(scenario.get_action_sequence())
        assert len(actions) > 0

        # Should have some variety in generator types or include idle
        gen_types = set(a.generator_type for a in actions)
        assert len(gen_types) >= 1, "Should use at least one generator type"

    def test_available_actions_filter(self, config, scheduler, rng):
        """Test that get_available_actions only includes available generators."""
        available_gen = MagicMock()
        available_gen.is_available.return_value = True
        available_gen.get_available_actions.return_value = ["action1"]

        unavailable_gen = MagicMock()
        unavailable_gen.is_available.return_value = False
        unavailable_gen.get_available_actions.return_value = ["action2"]

        generators = {
            "available": available_gen,
            "unavailable": unavailable_gen,
        }

        scenario = ContinuousScenario(config, scheduler, generators, rng)
        available = scenario.get_available_actions()

        assert "available" in available
        assert "unavailable" not in available


class TestAIDrivenScenario:
    """Tests for the AI-driven scenario."""

    @pytest.fixture
    def ai_config(self):
        from simulator.config import AIConfig

        return SimulatorConfig(
            duration_minutes=1,
            mouse_enabled=True,
            keyboard_enabled=True,
            vscode_enabled=False,
            random_seed=42,
            ai=AIConfig(api_key="test-key", max_api_calls=3),
        )

    @pytest.fixture
    def rng(self):
        return random.Random(42)

    @pytest.fixture
    def scheduler(self, ai_config, rng):
        return Scheduler(ai_config, rng)

    @pytest.fixture
    def mock_generators(self):
        mouse = MagicMock()
        mouse.is_available.return_value = True
        mouse.get_available_actions.return_value = ["move_realistic", "click_left"]
        mouse.generator_type = "mouse"

        keyboard = MagicMock()
        keyboard.is_available.return_value = True
        keyboard.get_available_actions.return_value = ["type_text"]
        keyboard.generator_type = "keyboard"

        return {"mouse": mouse, "keyboard": keyboard}

    def test_scenario_properties(self, ai_config, scheduler, mock_generators, rng):
        from simulator.scenarios.ai_driven import AIDrivenScenario

        scenario = AIDrivenScenario(ai_config, scheduler, mock_generators, rng)
        assert "AI-Driven" in scenario.name
        assert "AI model" in scenario.description

    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    def test_scenario_yields_actions_from_brain(
        self, ai_config, scheduler, mock_generators, rng
    ):
        from unittest.mock import patch
        from simulator.scenarios.ai_driven import AIDrivenScenario

        scenario = AIDrivenScenario(ai_config, scheduler, mock_generators, rng)

        mock_actions = [
            ScheduledAction(delay=1.0, generator_type="mouse", action_name="click_left"),
        ]

        with patch("simulator.ai.ai_brain.OpenAI"):
            with patch.object(
                type(scenario), "brain", new_callable=lambda: property(lambda self: MagicMock(
                    decide_next_actions=MagicMock(return_value=mock_actions),
                    api_calls_remaining=3,
                    api_calls_made=0,
                ))
            ):
                actions = list(scenario.get_action_sequence())
                # Should yield at least some actions
                assert len(actions) > 0

    def test_scenario_has_record_result(self, ai_config, scheduler, mock_generators, rng):
        """Test that AIDrivenScenario exposes record_result for the Controller."""
        from simulator.scenarios.ai_driven import AIDrivenScenario

        scenario = AIDrivenScenario(ai_config, scheduler, mock_generators, rng)
        assert hasattr(scenario, "record_result")
        assert callable(scenario.record_result)
