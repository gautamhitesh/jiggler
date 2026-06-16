"""Structured event logger for the Developer Activity Simulator.

Writes activity events as JSON Lines (.jsonl) files for efficient
append-only logging during long-duration test runs.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from simulator.config import LogLevel, SimulatorConfig
    from simulator.generators.base import ActivityEvent


class EventLogger:
    """Thread-safe structured event logger.

    Writes events as JSON Lines to a .jsonl file and also logs
    to Python's standard logging for console output.

    Attributes:
        log_dir: Directory where log files are stored.
        session_id: Unique identifier for this test session.
    """

    def __init__(self, config: SimulatorConfig, session_id: str | None = None) -> None:
        """Initialize the event logger.

        Args:
            config: Simulator configuration.
            session_id: Optional session identifier. If not provided,
                       a timestamp-based ID will be generated.
        """
        self.config = config
        self.session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path(config.log_dir)
        self._lock = threading.Lock()
        self._event_count = 0
        self._error_count = 0
        self._start_time = datetime.now(timezone.utc)

        # Set up file logging
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file_path = self.log_dir / f"session_{self.session_id}.jsonl"
        self._log_file = open(self._log_file_path, "a", encoding="utf-8")

        # Set up Python standard logging
        self._setup_console_logging(config.logging_verbosity)

        self.logger = logging.getLogger("EventLogger")
        self.logger.info(
            "Event logger initialized. Session: %s, Log file: %s",
            self.session_id,
            self._log_file_path,
        )

    def _setup_console_logging(self, verbosity: LogLevel) -> None:
        """Configure Python standard logging based on verbosity level.

        Args:
            verbosity: Desired logging verbosity.
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        level = level_map.get(verbosity.value, logging.INFO)

        # Configure root logger
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(level)
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)-8s] %(name)-20s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)
        root_logger.setLevel(level)

    def log_event(self, event: ActivityEvent) -> None:
        """Log an activity event to the JSONL file and console.

        Thread-safe: multiple generators can log concurrently.

        Args:
            event: The activity event to log.
        """
        event_dict = event.to_dict()

        with self._lock:
            self._event_count += 1
            if not event.success:
                self._error_count += 1

            # Write to JSONL file
            line = json.dumps(event_dict, default=str)
            self._log_file.write(line + "\n")
            self._log_file.flush()

        # Console logging
        if event.success:
            self.logger.debug(
                "[%s] %s -- %s",
                event.event_type,
                event.action,
                event.application or "system",
            )
        else:
            self.logger.warning(
                "[%s] %s FAILED -- %s: %s",
                event.event_type,
                event.action,
                event.application or "system",
                event.error_message,
            )

    def log_session_start(self, config_summary: dict[str, Any]) -> None:
        """Log a session start marker event.

        Args:
            config_summary: Summary of the configuration used.
        """
        start_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "session",
            "action": "start",
            "application": "",
            "success": True,
            "details": {
                "session_id": self.session_id,
                "config": config_summary,
            },
        }
        with self._lock:
            line = json.dumps(start_event, default=str)
            self._log_file.write(line + "\n")
            self._log_file.flush()

        self.logger.info("Session started: %s", self.session_id)

    def log_session_end(self, reason: str = "completed") -> None:
        """Log a session end marker event.

        Args:
            reason: Reason for session end (e.g., 'completed', 'interrupted', 'error').
        """
        end_time = datetime.now(timezone.utc)
        runtime = (end_time - self._start_time).total_seconds()

        end_event = {
            "timestamp": end_time.isoformat(),
            "event_type": "session",
            "action": "end",
            "application": "",
            "success": True,
            "details": {
                "session_id": self.session_id,
                "reason": reason,
                "total_events": self._event_count,
                "total_errors": self._error_count,
                "runtime_seconds": runtime,
            },
        }
        with self._lock:
            line = json.dumps(end_event, default=str)
            self._log_file.write(line + "\n")
            self._log_file.flush()

        self.logger.info(
            "Session ended: %s (reason=%s, events=%d, errors=%d, runtime=%.1fs)",
            self.session_id,
            reason,
            self._event_count,
            self._error_count,
            runtime,
        )

    @property
    def log_file_path(self) -> Path:
        """Path to the current session log file."""
        return self._log_file_path

    @property
    def event_count(self) -> int:
        """Total number of events logged in this session."""
        return self._event_count

    @property
    def error_count(self) -> int:
        """Total number of error events in this session."""
        return self._error_count

    def close(self) -> None:
        """Close the log file. Call this during shutdown."""
        with self._lock:
            if self._log_file and not self._log_file.closed:
                self._log_file.close()
                self.logger.info("Log file closed: %s", self._log_file_path)

    def __enter__(self) -> EventLogger:
        return self

    def __exit__(self, *args) -> None:
        self.close()
