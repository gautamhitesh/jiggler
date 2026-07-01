"""Controller — central orchestrator for the Developer Activity Simulator.

Coordinates test execution by initializing generators, running the
selected scenario, handling graceful shutdown, and generating reports.
"""

from __future__ import annotations

import logging
import platform
import random
import signal
import sys
import time
from pyautogui import FailSafeException
from datetime import datetime, timezone
from typing import Any

from simulator import __tool_name__, __version__
from simulator.config import ScenarioType, SimulatorConfig
from simulator.generators.app_interaction import AppInteractionGenerator
from simulator.generators.base import ActivityEvent, BaseGenerator
from simulator.generators.keyboard import KeyboardGenerator
from simulator.generators.mouse import MouseGenerator
from simulator.generators.vscode_adapter import VSCodeAdapter
from simulator.logging.event_logger import EventLogger
from simulator.reporting.reporter import Reporter
from simulator.scenarios.base import BaseScenario
from simulator.scenarios.continuous import ContinuousScenario
from simulator.scenarios.edge_timeout import EdgeTimeoutScenario
from simulator.scenarios.intermittent import IntermittentScenario
from simulator.scenarios.long_duration import LongDurationScenario
from simulator.scenarios.randomized import RandomizedScenario
from simulator.scenarios.ai_driven import AIDrivenScenario
from simulator.scheduler import Scheduler
from simulator.safety.sandbox import SandboxManager
from simulator.safety.presence_detector import PresenceDetector

logger = logging.getLogger(__name__)


class Controller:
    """Central orchestrator for test execution.

    Initializes all components, runs the selected scenario, handles
    errors and interrupts, and produces final reports.
    """

    # Map scenario types to their implementation classes
    SCENARIO_MAP: dict[ScenarioType, type[BaseScenario]] = {
        ScenarioType.CONTINUOUS: ContinuousScenario,
        ScenarioType.INTERMITTENT: IntermittentScenario,
        ScenarioType.EDGE_TIMEOUT: EdgeTimeoutScenario,
        ScenarioType.LONG_DURATION: LongDurationScenario,
        ScenarioType.RANDOMIZED: RandomizedScenario,
        ScenarioType.AI_DRIVEN: AIDrivenScenario,
    }

    def __init__(self, config: SimulatorConfig, dry_run: bool = False) -> None:
        """Initialize the controller.

        Args:
            config: Simulator configuration.
            dry_run: If True, log actions without executing them.
        """
        self.config = config
        self.dry_run = dry_run
        self._shutdown_requested = False
        self._start_time: float | None = None
        self._actions_executed = 0

        # Initialize seeded RNG
        if config.random_seed is not None:
            self.rng = random.Random(config.random_seed)
            logger.info("Using fixed random seed: %d", config.random_seed)
        else:
            self.rng = random.Random()
            logger.info("Using random seed (non-deterministic)")

        # Initialize event logger
        self.event_logger = EventLogger(config)

        # Initialize scheduler
        self.scheduler = Scheduler(config, self.rng)
        
        # Initialize safety systems
        self.sandbox = SandboxManager(config)
        self.presence_detector = None
        if config.safety.presence_detection_enabled:
            self.presence_detector = PresenceDetector(config)

        # Initialize generators
        self.generators: dict[str, BaseGenerator] = {}
        self._init_generators()

        # Initialize reporter
        self.reporter = Reporter(config)

        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def _init_generators(self) -> None:
        """Initialize activity generators based on configuration."""
        if self.config.mouse_enabled:
            mouse_gen = MouseGenerator(self.config, self.event_logger, self.rng)
            mouse_gen.dry_run = self.dry_run
            self.generators["mouse"] = mouse_gen
            logger.info("Mouse generator initialized")

        if self.config.keyboard_enabled:
            kbd_gen = KeyboardGenerator(self.config, self.event_logger, self.rng)
            kbd_gen.dry_run = self.dry_run
            self.generators["keyboard"] = kbd_gen
            logger.info("Keyboard generator initialized")

        if self.config.vscode_enabled:
            vscode_gen = VSCodeAdapter(self.config, self.event_logger, self.rng)
            vscode_gen.dry_run = self.dry_run
            self.generators["vscode"] = vscode_gen

            if vscode_gen.is_available():
                logger.info("VS Code adapter initialized")
            else:
                logger.warning("VS Code not found in PATH -- adapter will skip actions")

        # App interaction generator (always enabled if any other generator is)
        if self.generators:
            app_gen = AppInteractionGenerator(self.config, self.event_logger, self.rng)
            app_gen.dry_run = self.dry_run
            self.generators["app_interaction"] = app_gen
            logger.info("App interaction generator initialized")
            
        # Wire presence detector to all generators
        if self.presence_detector:
            for gen in self.generators.values():
                gen.presence_detector = self.presence_detector

    def _setup_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully.

        Args:
            signum: Signal number received.
            frame: Current stack frame (unused).
        """
        signal_name = signal.Signals(signum).name
        logger.warning("Received %s -- initiating graceful shutdown...", signal_name)
        self._shutdown_requested = True

    def _get_config_summary(self) -> dict[str, Any]:
        """Get a summary of the current configuration for logging.

        Returns:
            Dictionary of key config values.
        """
        return {
            "duration_minutes": self.config.duration_minutes,
            "scenario": self.config.scenario.value,
            "mouse_enabled": self.config.mouse_enabled,
            "keyboard_enabled": self.config.keyboard_enabled,
            "vscode_enabled": self.config.vscode_enabled,
            "idle_probability": self.config.idle_probability,
            "typing_speed_wpm": self.config.typing_speed_wpm,
            "random_seed": self.config.random_seed,
            "dry_run": self.dry_run,
        }

    def run(self) -> None:
        """Execute the simulation.

        This is the main entry point. It:
        1. Prints the startup banner
        2. Logs session start
        3. Creates and runs the selected scenario
        4. Handles errors and interrupts
        5. Generates reports
        6. Cleans up
        """
        self._print_banner()
        self._start_time = time.monotonic()

        # Log session start
        self.event_logger.log_session_start(self._get_config_summary())

        # Resolve scenario
        scenario_cls = self.SCENARIO_MAP.get(self.config.scenario)
        if scenario_cls is None:
            logger.error("Unknown scenario: %s", self.config.scenario)
            self.event_logger.log_session_end("error")
            return

        scenario = scenario_cls(
            config=self.config,
            scheduler=self.scheduler,
            generators=self.generators,
            rng=self.rng,
        )

        logger.info("Starting scenario: %s", scenario.name)
        logger.info("Description: %s", scenario.description)
        logger.info("Duration: %d minutes", self.config.duration_minutes)
        if self.dry_run:
            logger.info("*** DRY RUN MODE -- no actual input events will be generated ***")

        # Set up sandbox
        self.sandbox.setup()
        
        # Start presence detector
        if self.presence_detector:
            self.presence_detector.start()

        # Execute scenario
        end_reason = "completed"
        try:
            self._execute_scenario(scenario)
        except KeyboardInterrupt:
            end_reason = "interrupted"
            logger.warning("Interrupted by user (KeyboardInterrupt)")
        except FailSafeException:
            end_reason = "interrupted"
            logger.warning("Interrupted by user (PyAutoGUI FailSafeException)")
        except Exception as e:
            end_reason = "error"
            logger.error("Simulation failed with error: %s", e, exc_info=True)

        # Finalize
        elapsed = time.monotonic() - self._start_time
        logger.info(
            "Simulation finished -- reason: %s, actions: %d, elapsed: %.1fs",
            end_reason,
            self._actions_executed,
            elapsed,
        )

        # Log session end
        self.event_logger.log_session_end(end_reason)

        # Generate reports
        self._generate_reports()

        # Cleanup
        if self.presence_detector:
            self.presence_detector.stop()
        self.sandbox.cleanup()
        self.event_logger.close()

    def _execute_scenario(self, scenario: BaseScenario) -> None:
        """Execute the action sequence from a scenario.

        Args:
            scenario: The scenario instance to execute.
        """
        for action in scenario.get_action_sequence():
            if self._shutdown_requested:
                logger.info("Shutdown requested -- stopping action execution")
                break
                
            # Check user presence safety
            if self.presence_detector and self.presence_detector.is_user_active:
                logger.info("Safety: Real user activity detected — pausing...")
                self.presence_detector.wait_for_user_idle()
                logger.info("Safety: User idle — resuming execution")

            # Handle idle actions (just sleep)
            if action.generator_type == "idle":
                if not self.dry_run:
                    logger.debug("Idle: %s for %.1fs", action.action_name, action.delay)
                    time.sleep(action.delay)
                else:
                    logger.info("[DRY RUN] Idle: %s (%.1fs)", action.action_name, action.delay)
                continue

            # Handle health check markers
            if action.generator_type == "health_check":
                self._log_health_check()
                continue

            # Wait for the scheduled delay
            if action.delay > 0 and not self.dry_run:
                time.sleep(action.delay)

            # Execute the action on the appropriate generator
            generator = self.generators.get(action.generator_type)
            if generator is None:
                logger.warning(
                    "No generator for type '%s' -- skipping action '%s'",
                    action.generator_type,
                    action.action_name,
                )
                continue

            event = generator.execute(action.action_name)
            self._actions_executed += 1

            # Feed result back to AI brain if scenario supports it
            if hasattr(scenario, 'record_result'):
                scenario.record_result(action, event)

            # Periodic progress logging
            if self._actions_executed % 50 == 0:
                elapsed = time.monotonic() - (self._start_time or 0)
                logger.info(
                    "Progress: %d actions executed, %.0f seconds elapsed",
                    self._actions_executed,
                    elapsed,
                )

    def _log_health_check(self) -> None:
        """Log a health check event with system metrics."""
        import os

        try:
            import psutil

            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)
            cpu_percent = process.cpu_percent(interval=0.1)
        except ImportError:
            memory_mb = 0
            cpu_percent = 0

        elapsed = time.monotonic() - (self._start_time or 0)
        health_event = ActivityEvent(
            event_type="health_check",
            action="system_health_check",
            details={
                "actions_executed": self._actions_executed,
                "elapsed_seconds": round(elapsed, 1),
                "memory_mb": round(memory_mb, 1),
                "cpu_percent": round(cpu_percent, 1),
            },
        )
        self.event_logger.log_event(health_event)
        logger.info(
            "Health check: %d actions, %.0fs elapsed, %.1f MB memory, %.1f%% CPU",
            self._actions_executed,
            elapsed,
            memory_mb,
            cpu_percent,
        )

    def _generate_reports(self) -> None:
        """Generate post-run reports."""
        logger.info("Generating reports...")

        try:
            output_files = self.reporter.generate_reports(
                log_file_path=self.event_logger.log_file_path,
                session_id=self.event_logger.session_id,
            )

            for fmt, path in output_files.items():
                logger.info("Report generated [%s]: %s", fmt, path)

        except Exception as e:
            logger.error("Failed to generate reports: %s", e, exc_info=True)

    def _print_banner(self) -> None:
        """Print the startup identification banner."""
        tool = __tool_name__
        ver = "v" + __version__
        banner = f"""
+==================================================================+
|                                                                    |
|   {tool:^64s}   |
|   {ver:^64s}   |
|                                                                    |
|   This tool is intended solely for QA, testing, benchmarking,      |
|   and validation purposes in controlled environments.              |
|                                                                    |
+==================================================================+

  Platform:  {platform.system()} {platform.release()}
  Python:    {platform.python_version()}
  Scenario:  {self.config.scenario.value}
  Duration:  {self.config.duration_minutes} minutes
  Dry Run:   {self.dry_run}
  Seed:      {self.config.random_seed or 'random'}
"""
        print(banner)
