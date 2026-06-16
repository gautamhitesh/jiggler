"""Scenario A — Continuous Activity.

Constant interaction for N minutes with minimal idle periods.
"""

from __future__ import annotations

from typing import Iterator

from simulator.scenarios.base import BaseScenario
from simulator.scheduler import ScheduledAction


class ContinuousScenario(BaseScenario):
    """Continuous activity scenario — constant interaction with minimal idle.

    Designed to test monitoring system behavior under sustained activity.
    """

    @property
    def name(self) -> str:
        return "Scenario A — Continuous Activity"

    @property
    def description(self) -> str:
        return "Constant interaction for the configured duration with minimal idle periods."

    def get_action_sequence(self) -> Iterator[ScheduledAction]:
        """Generate continuous stream of actions.

        Yields:
            ScheduledAction with short, consistent delays between actions.
        """
        available = self.get_available_actions()
        yield from self.scheduler.generate_continuous_actions(
            duration_seconds=self.config.duration_seconds,
            available_actions=available,
        )
