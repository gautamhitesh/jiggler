"""Scenario F — AI-Driven Session.

An AI model decides what actions to perform next via tool calling,
creating unpredictable but contextually coherent human-like activity.
"""

from __future__ import annotations

import logging
from typing import Iterator

from simulator.ai.ai_brain import AIBrain
from simulator.scenarios.base import BaseScenario
from simulator.scheduler import ScheduledAction

logger = logging.getLogger(__name__)


class AIDrivenScenario(BaseScenario):
    """AI-driven scenario — LLM decides what to do next.

    Unlike deterministic or random scenarios, this uses an AI model
    (via OpenRouter) to decide the next actions through tool calling.
    The model receives context about recent actions and chooses what
    a real developer would do next.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._brain: AIBrain | None = None

    @property
    def name(self) -> str:
        return "Scenario F — AI-Driven Session"

    @property
    def description(self) -> str:
        return (
            f"AI model ({self.config.ai.model}) decides actions in real-time "
            f"via tool calling for human-like behavior."
        )

    @property
    def brain(self) -> AIBrain:
        """Lazily initialize the AI brain on first access."""
        if self._brain is None:
            self._brain = AIBrain(
                config=self.config,
                generators=self.generators,
                rng=self.rng,
            )
        return self._brain

    def get_action_sequence(self) -> Iterator[ScheduledAction]:
        """Generate actions by asking the AI model what to do next.

        The AI brain is called in a loop. Each call returns one or more
        actions. The loop continues until the configured duration is
        exceeded or the API call safety cap is reached.

        Yields:
            ScheduledAction objects decided by the AI model.
        """
        elapsed = 0.0
        duration = self.config.duration_seconds

        logger.info(
            "AI-driven scenario starting — model: %s, max_calls: %d",
            self.config.ai.model,
            self.config.ai.max_api_calls,
        )

        while elapsed < duration:
            # Check API call budget
            if self.brain.api_calls_remaining <= 0:
                logger.warning(
                    "API call budget exhausted (%d calls) — ending AI scenario",
                    self.brain.api_calls_made,
                )
                break

            # Ask the AI what to do next
            actions = self.brain.decide_next_actions()

            for action in actions:
                if elapsed >= duration:
                    break

                yield action
                elapsed += action.delay

        logger.info(
            "AI-driven scenario complete — %d API calls made, %.1fs elapsed",
            self.brain.api_calls_made,
            elapsed,
        )

    def record_result(
        self,
        action: ScheduledAction,
        event=None,
    ) -> None:
        """Record action result for AI context (called by Controller).

        This method is duck-typed — the Controller checks for its
        existence and calls it after each action to feed results back
        to the AI brain.

        Args:
            action: The action that was executed.
            event: The resulting ActivityEvent.
        """
        self.brain.record_action_result(action, event)
