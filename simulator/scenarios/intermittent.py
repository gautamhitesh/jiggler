"""Scenario B — Intermittent Activity.

Activity bursts followed by idle periods, mimicking natural work patterns.
"""

from __future__ import annotations

from typing import Iterator

from simulator.scenarios.base import BaseScenario
from simulator.scheduler import ScheduledAction


class IntermittentScenario(BaseScenario):
    """Intermittent activity scenario — bursts followed by idle periods.

    Designed to test monitoring system behavior with natural work patterns
    including breaks and context switches.
    """

    @property
    def name(self) -> str:
        return "Scenario B — Intermittent Activity"

    @property
    def description(self) -> str:
        return "Activity bursts followed by configurable idle periods."

    def get_action_sequence(self) -> Iterator[ScheduledAction]:
        """Generate intermittent bursts of activity with idle gaps.

        Yields:
            ScheduledAction with burst/idle pattern.
        """
        available = self.get_available_actions()
        yield from self.scheduler.generate_intermittent_actions(
            duration_seconds=self.config.duration_seconds,
            available_actions=available,
        )
