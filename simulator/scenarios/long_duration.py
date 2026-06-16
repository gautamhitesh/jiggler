"""Scenario D — Long Duration Session.

Execute activity patterns for multiple hours with periodic health
checks to verify system stability over extended periods.
"""

from __future__ import annotations

import logging
from typing import Iterator

from simulator.scenarios.base import BaseScenario
from simulator.scheduler import ScheduledAction

logger = logging.getLogger(__name__)

# Health check interval: log system status every 30 minutes
HEALTH_CHECK_INTERVAL = 1800  # seconds


class LongDurationScenario(BaseScenario):
    """Long duration scenario — extended multi-hour test sessions.

    Uses continuous activity patterns with periodic health check
    markers injected into the action stream. Designed to verify
    system stability, memory usage, and resource consumption over
    runs exceeding 8 hours.
    """

    @property
    def name(self) -> str:
        return "Scenario D — Long Duration Session"

    @property
    def description(self) -> str:
        return "Extended activity for multiple hours with periodic health checks."

    def get_action_sequence(self) -> Iterator[ScheduledAction]:
        """Generate long-duration actions with health check markers.

        Breaks the total duration into segments with health check
        points between them.

        Yields:
            ScheduledAction objects with health check markers.
        """
        available = self.get_available_actions()
        total_duration = self.config.duration_seconds
        elapsed = 0.0
        segment_num = 0

        while elapsed < total_duration:
            segment_num += 1
            segment_duration = min(HEALTH_CHECK_INTERVAL, total_duration - elapsed)

            logger.info(
                "Long duration segment %d starting (elapsed: %.0f / %.0f seconds)",
                segment_num,
                elapsed,
                total_duration,
            )

            # Generate continuous actions for this segment
            segment_elapsed = 0.0
            for action in self.scheduler.generate_continuous_actions(
                duration_seconds=segment_duration,
                available_actions=available,
            ):
                yield action
                segment_elapsed += action.delay

            elapsed += segment_duration

            # Health check marker
            if elapsed < total_duration:
                yield ScheduledAction(
                    delay=1.0,
                    generator_type="health_check",
                    action_name="system_health_check",
                )
                elapsed += 1.0
