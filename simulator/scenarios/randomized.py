"""Scenario E — Randomized Session.

Fully randomized mouse and keyboard actions with variable timing.
"""

from __future__ import annotations

from typing import Iterator

from simulator.scenarios.base import BaseScenario
from simulator.scheduler import ScheduledAction


class RandomizedScenario(BaseScenario):
    """Randomized scenario — fully random activity patterns.

    Designed to test monitoring system behavior under unpredictable
    workstation activity with variable timing between actions.
    """

    @property
    def name(self) -> str:
        return "Scenario E — Randomized Session"

    @property
    def description(self) -> str:
        return "Fully randomized action types and timing for unpredictable activity patterns."

    def get_action_sequence(self) -> Iterator[ScheduledAction]:
        """Generate fully randomized actions.

        Yields:
            ScheduledAction with random types and variable delays.
        """
        available = self.get_available_actions()
        yield from self.scheduler.generate_randomized_actions(
            duration_seconds=self.config.duration_seconds,
            available_actions=available,
        )
