"""Scenario C — Edge Timeout Validation.

Remains idle until just before the monitoring timeout threshold,
then generates activity to verify timeout reset behavior.
"""

from __future__ import annotations

from typing import Iterator

from simulator.scenarios.base import BaseScenario
from simulator.scheduler import ScheduledAction


class EdgeTimeoutScenario(BaseScenario):
    """Edge timeout scenario — test timeout boundary behavior.

    Designed to validate that the monitoring system correctly resets
    its timeout counter when activity occurs just before the threshold.
    """

    @property
    def name(self) -> str:
        return "Scenario C — Edge Timeout Validation"

    @property
    def description(self) -> str:
        return (
            "Idle until just before the timeout threshold, "
            "then generate activity to verify timeout reset."
        )

    def get_action_sequence(self) -> Iterator[ScheduledAction]:
        """Generate edge-timeout pattern actions.

        Yields:
            ScheduledAction with long idles followed by brief activity.
        """
        available = self.get_available_actions()
        yield from self.scheduler.generate_edge_timeout_actions(
            duration_seconds=self.config.duration_seconds,
            available_actions=available,
        )
