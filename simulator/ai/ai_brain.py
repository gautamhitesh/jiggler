"""AI Brain — LLM-powered action decision engine.

Uses OpenRouter API with tool calling to let any AI model decide
what human-like actions to perform next. The model receives tool
definitions auto-generated from existing generators and returns
tool_calls that are translated into ScheduledAction objects.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import TYPE_CHECKING, Any, Optional

from openai import OpenAI, APIError, APIConnectionError, RateLimitError

from simulator.ai.tool_registry import build_tool_schemas, parse_tool_name
from simulator.scheduler import ScheduledAction

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig
    from simulator.generators.base import ActivityEvent, BaseGenerator

logger = logging.getLogger(__name__)

# Default system prompt for the AI developer persona
_DEFAULT_SYSTEM_PROMPT = """\
You are simulating a real software developer working at their computer. Your job \
is to produce realistic, human-like workstation activity by calling the tools \
available to you.

Guidelines for realistic behavior:
- Alternate between different activity types naturally (don't spam the same action).
- Occasionally take short idle breaks — humans read, think, and sip coffee.
- When working in VS Code, follow natural flows: open a file → read/scroll → \
type code → save → switch tabs.
- Mix mouse and keyboard activity — real developers use both.
- Vary your pace: sometimes work in quick bursts, sometimes slow down.
- Don't be perfectly rhythmic — add natural variation.
- You can call multiple tools in a single response to create action sequences.

You will receive feedback about your previous actions to help you maintain context \
about what you've been doing. Use this to make coherent decisions.
"""


class AIBrain:
    """Central AI decision engine for the AI-driven scenario.

    Manages the OpenRouter API connection, constructs tool schemas from
    generators, maintains conversation context, and translates LLM
    tool_calls into ScheduledAction objects for execution.
    """

    def __init__(
        self,
        config: SimulatorConfig,
        generators: dict[str, BaseGenerator],
        rng: random.Random,
    ) -> None:
        """Initialize the AI brain.

        Args:
            config: Simulator configuration (includes AIConfig).
            generators: Map of generator_type → generator instance.
            rng: Seeded random number generator for thinking delays.

        Raises:
            ValueError: If no API key is provided via any source.
        """
        self.config = config
        self.ai_config = config.ai
        self.generators = generators
        self.rng = rng

        # Resolve API key: CLI/config > env var
        self._api_key = self.ai_config.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self._api_key:
            raise ValueError(
                "AI-driven scenario requires an OpenRouter API key. "
                "Provide it via --ai-api-key, config.yaml ai.api_key, "
                "or OPENROUTER_API_KEY environment variable."
            )

        # Initialize OpenAI client pointed at OpenRouter
        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self.ai_config.base_url,
        )

        # Build tool schemas from generators
        self._tools = build_tool_schemas(generators)

        # Conversation context (action history)
        self._action_history: list[dict[str, Any]] = []

        # API call tracking
        self._api_calls_made = 0

        # System prompt
        self._system_prompt = self.ai_config.system_prompt or _DEFAULT_SYSTEM_PROMPT

        logger.info(
            "AI Brain initialized — model: %s, tools: %d, max_calls: %d",
            self.ai_config.model,
            len(self._tools),
            self.ai_config.max_api_calls,
        )

    @property
    def api_calls_made(self) -> int:
        """Number of API calls made so far."""
        return self._api_calls_made

    @property
    def api_calls_remaining(self) -> int:
        """Number of API calls remaining before hitting the safety cap."""
        return max(0, self.ai_config.max_api_calls - self._api_calls_made)

    def decide_next_actions(self) -> list[ScheduledAction]:
        """Ask the AI model what actions to perform next.

        Makes a single API call with the current context and tool
        definitions. Parses the model's tool_calls into ScheduledAction
        objects.

        Returns:
            List of ScheduledAction objects to execute. May be empty if
            the model doesn't call any tools or if the API call limit
            has been reached.
        """
        if self._api_calls_made >= self.ai_config.max_api_calls:
            logger.warning(
                "API call limit reached (%d/%d) — no more AI decisions",
                self._api_calls_made,
                self.ai_config.max_api_calls,
            )
            return []

        messages = self._build_messages()

        try:
            response = self._call_api(messages)
            self._api_calls_made += 1

            actions = self._parse_tool_calls(response)

            if not actions:
                # Model didn't call any tools — inject a default idle
                logger.debug("AI returned no tool calls — inserting default idle")
                actions = [
                    ScheduledAction(
                        delay=self.rng.uniform(2.0, 5.0),
                        generator_type="idle",
                        action_name="ai_thinking",
                    )
                ]

            logger.info(
                "AI decision #%d: %d action(s) — [%s]",
                self._api_calls_made,
                len(actions),
                ", ".join(f"{a.generator_type}.{a.action_name}" for a in actions),
            )
            return actions

        except (APIError, APIConnectionError, RateLimitError) as e:
            logger.error("OpenRouter API error: %s", e)
            self._api_calls_made += 1
            # Return a safe idle action on API error
            return [
                ScheduledAction(
                    delay=self.rng.uniform(3.0, 8.0),
                    generator_type="idle",
                    action_name="api_error_recovery",
                )
            ]
        except Exception as e:
            logger.error("Unexpected error in AI brain: %s", e, exc_info=True)
            self._api_calls_made += 1
            return [
                ScheduledAction(
                    delay=self.rng.uniform(3.0, 8.0),
                    generator_type="idle",
                    action_name="error_recovery",
                )
            ]

    def record_action_result(
        self,
        action: ScheduledAction,
        event: Optional[ActivityEvent] = None,
    ) -> None:
        """Record the result of an executed action for context.

        Maintains a sliding window of the last N actions to provide
        the AI with context about what has happened.

        Args:
            action: The action that was executed.
            event: The resulting activity event (may be None for idles).
        """
        entry = {
            "action": f"{action.generator_type}.{action.action_name}",
            "delay": round(action.delay, 2),
        }

        if event is not None:
            entry["success"] = event.success
            if event.details:
                # Include a subset of details for context
                entry["details"] = {
                    k: v for k, v in event.details.items()
                    if k not in ("dry_run",)
                }
            if event.error_message:
                entry["error"] = event.error_message

        self._action_history.append(entry)

        # Trim to context window size
        max_history = self.ai_config.context_window
        if len(self._action_history) > max_history:
            self._action_history = self._action_history[-max_history:]

    def _build_messages(self) -> list[dict[str, str]]:
        """Build the messages array for the API call.

        Returns:
            List of message dicts with system prompt and action context.
        """
        messages = [
            {"role": "system", "content": self._system_prompt},
        ]

        # Add action history as context
        if self._action_history:
            history_text = "Recent actions you've performed:\n"
            for i, entry in enumerate(self._action_history, 1):
                status = "✓" if entry.get("success", True) else "✗"
                history_text += f"  {i}. [{status}] {entry['action']}"
                if "details" in entry:
                    details_str = json.dumps(entry["details"], default=str)
                    if len(details_str) <= 100:
                        history_text += f" — {details_str}"
                history_text += "\n"

            history_text += (
                "\nDecide what to do next. Be natural and varied. "
                "Call one or more tools to perform actions."
            )
            messages.append({"role": "user", "content": history_text})
        else:
            messages.append({
                "role": "user",
                "content": (
                    "You're starting a new work session at your computer. "
                    "Begin by performing some natural startup actions — "
                    "maybe launch VS Code, move the mouse, open a file, etc. "
                    "Call one or more tools to get started."
                ),
            })

        return messages

    def _call_api(self, messages: list[dict[str, str]]) -> Any:
        """Make the API call to OpenRouter.

        Args:
            messages: Messages array for the chat completion.

        Returns:
            The API response object.
        """
        logger.debug(
            "Calling OpenRouter API — model: %s, messages: %d, tools: %d",
            self.ai_config.model,
            len(messages),
            len(self._tools),
        )

        response = self._client.chat.completions.create(
            model=self.ai_config.model,
            messages=messages,
            tools=self._tools,
            tool_choice="required",
            temperature=self.ai_config.temperature,
            extra_headers={
                "HTTP-Referer": "https://github.com/gautamhitesh/jiggler",
                "X-Title": "Jiggler Developer Activity Simulator",
            },
        )

        return response

    def _parse_tool_calls(self, response: Any) -> list[ScheduledAction]:
        """Parse tool_calls from the API response into ScheduledAction objects.

        Args:
            response: The OpenAI-compatible API response.

        Returns:
            List of ScheduledAction objects.
        """
        actions: list[ScheduledAction] = []

        if not response.choices:
            logger.warning("API response has no choices")
            return actions

        message = response.choices[0].message

        if not message.tool_calls:
            logger.debug("API response has no tool_calls")
            return actions

        for tool_call in message.tool_calls:
            try:
                tool_name = tool_call.function.name
                arguments_str = tool_call.function.arguments or "{}"

                try:
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError:
                    arguments = {}

                gen_type, action_name = parse_tool_name(tool_name)

                # Handle meta-tools
                if gen_type == "meta":
                    duration = float(arguments.get("duration_seconds", 3.0))
                    duration = max(0.5, min(30.0, duration))  # Clamp
                    actions.append(
                        ScheduledAction(
                            delay=duration,
                            generator_type="idle",
                            action_name=f"ai_{action_name}",
                        )
                    )
                    continue

                # Validate generator exists
                if gen_type not in self.generators:
                    logger.warning(
                        "AI called unknown generator '%s' — skipping", gen_type
                    )
                    continue

                # Validate action exists
                generator = self.generators[gen_type]
                if action_name not in generator.get_available_actions():
                    logger.warning(
                        "AI called unknown action '%s.%s' — skipping",
                        gen_type,
                        action_name,
                    )
                    continue

                # Add a natural thinking delay before the action
                delay = self.rng.uniform(
                    self.ai_config.thinking_delay_min,
                    self.ai_config.thinking_delay_max,
                )

                actions.append(
                    ScheduledAction(
                        delay=delay,
                        generator_type=gen_type,
                        action_name=action_name,
                    )
                )

            except ValueError as e:
                logger.warning("Failed to parse tool call '%s': %s", tool_call, e)
                continue

        return actions
