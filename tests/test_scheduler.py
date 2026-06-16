"""Tests for the scheduler module."""

from __future__ import annotations

import random

import pytest

from simulator.config import SimulatorConfig
from simulator.scheduler import ScheduledAction, Scheduler


class TestScheduler:
    """Tests for the action scheduler."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return SimulatorConfig(
            duration_minutes=1,
            mouse_enabled=True,
            keyboard_enabled=True,
            vscode_enabled=False,
            idle_probability=0.25,
            random_seed=42,
        )

    @pytest.fixture
    def rng(self):
        """Create a seeded RNG."""
        return random.Random(42)

    @pytest.fixture
    def scheduler(self, config, rng):
        """Create a scheduler instance."""
        return Scheduler(config, rng)

    @pytest.fixture
    def available_actions(self):
        """Sample available actions map."""
        return {
            "mouse": ["move_realistic", "move_random", "click_left"],
            "keyboard": ["type_text", "press_key"],
            "app_interaction": ["alt_tab", "focus_change"],
        }

    def test_enabled_generators(self, scheduler):
        """Test that enabled generators match config."""
        enabled = scheduler.enabled_generators
        assert "mouse" in enabled
        assert "keyboard" in enabled
        assert "vscode" not in enabled
        assert "app_interaction" in enabled

    def test_continuous_actions_fill_duration(self, scheduler, available_actions):
        """Test that continuous actions fill the specified duration."""
        duration = 10.0  # seconds
        actions = list(
            scheduler.generate_continuous_actions(duration, available_actions)
        )

        assert len(actions) > 0
        total_delay = sum(a.delay for a in actions)
        # Total delay should be approximately equal to or greater than duration
        assert total_delay >= duration * 0.8

    def test_continuous_actions_are_valid(self, scheduler, available_actions):
        """Test that continuous actions reference valid generators and actions."""
        actions = list(
            scheduler.generate_continuous_actions(5.0, available_actions)
        )

        for action in actions:
            assert isinstance(action, ScheduledAction)
            assert action.generator_type in available_actions
            assert action.action_name in available_actions[action.generator_type]
            assert action.delay > 0

    def test_intermittent_actions_have_idle_periods(self, available_actions):
        """Test that intermittent actions include idle periods.

        Uses a longer duration (10 min) and shorter burst/idle settings
        so the pattern has time to produce both burst and idle phases.
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

        actions = list(
            scheduler.generate_intermittent_actions(600.0, available_actions)
        )

        idle_actions = [a for a in actions if a.generator_type == "idle"]
        non_idle_actions = [a for a in actions if a.generator_type != "idle"]

        assert len(idle_actions) > 0, "Should have idle periods"
        assert len(non_idle_actions) > 0, "Should have active periods"

    def test_edge_timeout_actions_have_long_idles(self, scheduler, available_actions):
        """Test that edge timeout actions have long idle periods."""
        actions = list(
            scheduler.generate_edge_timeout_actions(600.0, available_actions)
        )

        idle_actions = [a for a in actions if a.generator_type == "idle"]
        assert len(idle_actions) > 0

        # At least some idle periods should be close to the timeout threshold
        long_idles = [a for a in idle_actions if a.delay > 100]
        assert len(long_idles) > 0

    def test_randomized_actions_have_variety(self, available_actions):
        """Test that randomized actions use multiple generator types.

        Uses a longer duration to ensure enough actions are generated
        to see variety across generator types.
        """
        config = SimulatorConfig(
            duration_minutes=5,
            mouse_enabled=True,
            keyboard_enabled=True,
            vscode_enabled=False,
            idle_probability=0.1,
            random_seed=42,
        )
        rng = random.Random(42)
        scheduler = Scheduler(config, rng)

        actions = list(
            scheduler.generate_randomized_actions(300.0, available_actions)
        )

        generator_types = set(a.generator_type for a in actions if a.generator_type != "idle")
        assert len(generator_types) >= 2, "Should use multiple generator types"

    def test_deterministic_with_same_seed(self, config, available_actions):
        """Test that same seed produces same action sequence."""
        rng1 = random.Random(42)
        scheduler1 = Scheduler(config, rng1)
        actions1 = list(
            scheduler1.generate_randomized_actions(10.0, available_actions)
        )

        rng2 = random.Random(42)
        scheduler2 = Scheduler(config, rng2)
        actions2 = list(
            scheduler2.generate_randomized_actions(10.0, available_actions)
        )

        assert len(actions1) == len(actions2)
        for a1, a2 in zip(actions1, actions2):
            assert a1.generator_type == a2.generator_type
            assert a1.action_name == a2.action_name
            assert abs(a1.delay - a2.delay) < 1e-10

    def test_different_seeds_produce_different_sequences(self, config, available_actions):
        """Test that different seeds produce different action sequences.

        Compares both action names and delays — with different seeds,
        at least the timing (delays) should differ even if by chance
        the same action names are selected.
        """
        rng1 = random.Random(42)
        scheduler1 = Scheduler(config, rng1)
        actions1 = list(
            scheduler1.generate_randomized_actions(60.0, available_actions)
        )

        rng2 = random.Random(99)
        scheduler2 = Scheduler(config, rng2)
        actions2 = list(
            scheduler2.generate_randomized_actions(60.0, available_actions)
        )

        # Compare both names and delays — at least one pair should differ
        has_difference = False
        min_len = min(len(actions1), len(actions2))
        for a1, a2 in zip(actions1[:min_len], actions2[:min_len]):
            if a1.action_name != a2.action_name or abs(a1.delay - a2.delay) > 1e-10:
                has_difference = True
                break

        assert has_difference or len(actions1) != len(actions2), \
            "Different seeds should produce different sequences"

    def test_scheduled_action_dataclass(self):
        """Test ScheduledAction dataclass."""
        action = ScheduledAction(
            delay=1.5,
            generator_type="mouse",
            action_name="move_realistic",
        )
        assert action.delay == 1.5
        assert action.generator_type == "mouse"
        assert action.action_name == "move_realistic"
