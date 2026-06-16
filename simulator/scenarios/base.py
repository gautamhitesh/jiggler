"""Abstract base class for test scenarios.

Each scenario defines a specific pattern of activity generation
(continuous, intermittent, edge-timeout, etc.) by configuring
the scheduler and selecting appropriate actions.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig
    from simulator.generators.base import BaseGenerator
    from simulator.scheduler import Scheduler, ScheduledAction


class BaseScenario(ABC):
    """Abstract base class for test scenarios.

    Scenarios configure the scheduler with a specific activity pattern
    and yield a sequence of scheduled actions for the controller to execute.
    """

    def __init__(
        self,
        config: SimulatorConfig,
        scheduler: Scheduler,
        generators: dict[str, BaseGenerator],
        rng: random.Random,
    ) -> None:
        """Initialize the scenario.

        Args:
            config: Simulator configuration.
            scheduler: Action scheduler instance.
            generators: Map of generator_type -> generator instance.
            rng: Seeded random number generator.
        """
        self.config = config
        self.scheduler = scheduler
        self.generators = generators
        self.rng = rng

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable scenario name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of what this scenario tests."""
        ...

    def get_available_actions(self) -> dict[str, list[str]]:
        """Build a map of generator_type -> available action names.

        Only includes enabled generators.

        Returns:
            Dictionary mapping generator types to their available actions.
        """
        actions = {}
        for gen_type, generator in self.generators.items():
            if generator.is_available():
                available = generator.get_available_actions()
                if available:
                    actions[gen_type] = available
        return actions

    @abstractmethod
    def get_action_sequence(self) -> Iterator[ScheduledAction]:
        """Generate the sequence of actions for this scenario.

        Yields:
            ScheduledAction objects in chronological order.
        """
        ...
