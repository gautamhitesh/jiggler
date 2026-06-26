"""Action scheduler for the Developer Activity Simulator.

Determines when and what actions occur based on the active scenario
and configuration parameters.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator, Optional

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig


@dataclass
class ScheduledAction:
    """An action scheduled for execution at a specific time.

    Attributes:
        delay: Seconds to wait before executing this action.
        generator_type: Which generator should execute ('mouse', 'keyboard', etc.).
        action_name: Specific action to execute (e.g., 'move_realistic', 'type_text').
    """

    delay: float
    generator_type: str
    action_name: str


class Scheduler:
    """Determines when and what actions occur during a simulation.

    The scheduler generates a stream of ScheduledAction objects based on
    the active scenario profile. It uses a seeded RNG for reproducibility.
    """

    def __init__(self, config: SimulatorConfig, rng: random.Random) -> None:
        """Initialize the scheduler.

        Args:
            config: Simulator configuration.
            rng: Seeded random number generator.
        """
        self.config = config
        self.rng = rng
        self._enabled_generators: list[str] = []

        # Build list of enabled generators
        if config.mouse_enabled:
            self._enabled_generators.append("mouse")
        if config.keyboard_enabled:
            self._enabled_generators.append("keyboard")
        if config.vscode_enabled:
            self._enabled_generators.append("vscode")
        # App interaction is always available if any other generator is enabled
        if self._enabled_generators:
            self._enabled_generators.append("app_interaction")

    @property
    def enabled_generators(self) -> list[str]:
        """List of enabled generator type identifiers."""
        return list(self._enabled_generators)

    def generate_continuous_actions(
        self,
        duration_seconds: float,
        available_actions: dict[str, list[str]],
    ) -> Iterator[ScheduledAction]:
        """Generate a continuous stream of actions for the given duration.

        Minimal idle periods — constant activity.

        Args:
            duration_seconds: Total duration to fill with actions.
            available_actions: Map of generator_type -> list of action names.

        Yields:
            ScheduledAction objects in chronological order.
        """
        elapsed = 0.0
        while elapsed < duration_seconds:
            generator_type = self._pick_generator(available_actions)
            action_name = self.rng.choice(available_actions[generator_type])
            delay = self.rng.uniform(0.5, 2.0)

            yield ScheduledAction(
                delay=delay,
                generator_type=generator_type,
                action_name=action_name,
            )
            elapsed += delay

    def generate_intermittent_actions(
        self,
        duration_seconds: float,
        available_actions: dict[str, list[str]],
    ) -> Iterator[ScheduledAction]:
        """Generate bursts of activity followed by idle periods.

        Args:
            duration_seconds: Total duration to fill.
            available_actions: Map of generator_type -> list of action names.

        Yields:
            ScheduledAction objects with burst/idle patterns.
        """
        elapsed = 0.0
        cfg = self.config.intermittent

        while elapsed < duration_seconds:
            # Activity burst
            burst_duration = self.rng.uniform(cfg.burst_duration_min, cfg.burst_duration_max)
            burst_elapsed = 0.0

            while burst_elapsed < burst_duration and elapsed < duration_seconds:
                generator_type = self._pick_generator(available_actions)
                action_name = self.rng.choice(available_actions[generator_type])
                delay = self.rng.uniform(0.5, 3.0)

                yield ScheduledAction(
                    delay=delay,
                    generator_type=generator_type,
                    action_name=action_name,
                )
                burst_elapsed += delay
                elapsed += delay

            # Idle period
            if elapsed < duration_seconds:
                idle_duration = self.rng.uniform(cfg.idle_duration_min, cfg.idle_duration_max)
                idle_duration = min(idle_duration, duration_seconds - elapsed)

                yield ScheduledAction(
                    delay=idle_duration,
                    generator_type="idle",
                    action_name="idle_period",
                )
                elapsed += idle_duration

    def generate_edge_timeout_actions(
        self,
        duration_seconds: float,
        available_actions: dict[str, list[str]],
    ) -> Iterator[ScheduledAction]:
        """Generate actions that test timeout edge cases.

        Idle until just before the timeout threshold, then generate
        activity to verify the timeout reset behavior.

        Args:
            duration_seconds: Total duration.
            available_actions: Map of generator_type -> list of action names.

        Yields:
            ScheduledAction objects with edge-timeout pattern.
        """
        elapsed = 0.0
        cfg = self.config.edge_timeout
        idle_until = cfg.timeout_threshold_seconds - cfg.activity_delta_seconds

        while elapsed < duration_seconds:
            # Idle until just before timeout
            idle_time = min(idle_until, duration_seconds - elapsed)
            if idle_time > 0:
                yield ScheduledAction(
                    delay=idle_time,
                    generator_type="idle",
                    action_name="idle_until_timeout",
                )
                elapsed += idle_time

            # Burst of activity to reset timeout
            if elapsed < duration_seconds:
                burst_count = self.rng.randint(3, 8)
                for _ in range(burst_count):
                    if elapsed >= duration_seconds:
                        break
                    generator_type = self._pick_generator(available_actions)
                    action_name = self.rng.choice(available_actions[generator_type])
                    delay = self.rng.uniform(0.5, 2.0)

                    yield ScheduledAction(
                        delay=delay,
                        generator_type=generator_type,
                        action_name=action_name,
                    )
                    elapsed += delay

    def generate_randomized_actions(
        self,
        duration_seconds: float,
        available_actions: dict[str, list[str]],
    ) -> Iterator[ScheduledAction]:
        """Generate fully randomized actions with variable timing.

        Args:
            duration_seconds: Total duration.
            available_actions: Map of generator_type -> list of action names.

        Yields:
            ScheduledAction objects with random patterns.
        """
        elapsed = 0.0
        while elapsed < duration_seconds:
            # Randomly decide: action or idle
            if self.rng.random() < self.config.idle_probability:
                idle_time = self.rng.uniform(5.0, 20.0)
                idle_time = min(idle_time, duration_seconds - elapsed)
                yield ScheduledAction(
                    delay=idle_time,
                    generator_type="idle",
                    action_name="random_idle",
                )
                elapsed += idle_time
            else:
                generator_type = self._pick_generator(available_actions)
                action_name = self.rng.choice(available_actions[generator_type])
                delay = self.rng.uniform(0.3, 5.0)

                yield ScheduledAction(
                    delay=delay,
                    generator_type=generator_type,
                    action_name=action_name,
                )
                elapsed += delay

    def _pick_generator(self, available_actions: dict[str, list[str]]) -> str:
        """Pick a random enabled generator that has available actions.

        Args:
            available_actions: Map of generator_type -> list of action names.

        Returns:
            A generator type string.
        """
        valid = [g for g in self._enabled_generators if g in available_actions and available_actions[g]]
        if not valid:
            # Fallback: pick from whatever is available
            valid = [g for g in available_actions if available_actions[g]]
        return self.rng.choice(valid) if valid else "mouse"
