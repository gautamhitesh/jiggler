"""Configuration models for the Developer Activity Simulator.

Uses Pydantic for validation and YAML for file-based configuration.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class ScenarioType(str, Enum):
    """Supported test scenarios."""

    CONTINUOUS = "continuous"
    INTERMITTENT = "intermittent"
    EDGE_TIMEOUT = "edge_timeout"
    LONG_DURATION = "long_duration"
    RANDOMIZED = "randomized"
    AI_DRIVEN = "ai_driven"


class LogLevel(str, Enum):
    """Logging verbosity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ReportFormat(str, Enum):
    """Report output formats."""

    JSON = "json"
    CSV = "csv"
    HTML = "html"


class VSCodeConfig(BaseModel):
    """VS Code adapter configuration."""

    workspace_path: str = "./test_workspace"
    auto_save_interval: int = Field(default=30, ge=5, description="Seconds between auto-saves")


class EdgeTimeoutConfig(BaseModel):
    """Edge timeout scenario configuration."""

    timeout_threshold_seconds: int = Field(
        default=300, ge=10, description="Monitoring system timeout threshold in seconds"
    )
    activity_delta_seconds: int = Field(
        default=10, ge=1, description="Seconds before timeout to generate activity"
    )


class IntermittentConfig(BaseModel):
    """Intermittent scenario configuration."""

    burst_duration_min: int = Field(default=120, ge=10, description="Min burst duration in seconds")
    burst_duration_max: int = Field(default=300, ge=10, description="Max burst duration in seconds")
    idle_duration_min: int = Field(default=60, ge=5, description="Min idle duration in seconds")
    idle_duration_max: int = Field(default=180, ge=5, description="Max idle duration in seconds")

    @field_validator("burst_duration_max")
    @classmethod
    def burst_max_gte_min(cls, v: int, info) -> int:
        if "burst_duration_min" in info.data and v < info.data["burst_duration_min"]:
            raise ValueError("burst_duration_max must be >= burst_duration_min")
        return v

    @field_validator("idle_duration_max")
    @classmethod
    def idle_max_gte_min(cls, v: int, info) -> int:
        if "idle_duration_min" in info.data and v < info.data["idle_duration_min"]:
            raise ValueError("idle_duration_max must be >= idle_duration_min")
        return v


class AIConfig(BaseModel):
    """AI-driven scenario configuration.

    Controls the OpenRouter API integration for LLM-powered
    action selection via tool calling.
    """

    api_key: Optional[str] = Field(
        default=None, description="OpenRouter API key (overridden by CLI/env var)"
    )
    model: str = Field(
        default="google/gemini-2.0-flash",
        description="OpenRouter model identifier",
    )
    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
    )
    system_prompt: Optional[str] = Field(
        default=None, description="Custom AI persona system prompt override"
    )
    temperature: float = Field(
        default=0.9, ge=0.0, le=2.0,
        description="Sampling temperature — higher is more random/human-like",
    )
    context_window: int = Field(
        default=10, ge=1, le=50,
        description="Number of past actions to include as conversation context",
    )
    max_api_calls: int = Field(
        default=500, ge=1,
        description="Maximum API calls per session (safety cost cap)",
    )
    thinking_delay_min: float = Field(
        default=1.0, ge=0.0,
        description="Minimum seconds between AI decisions (simulates thinking)",
    )
    thinking_delay_max: float = Field(
        default=5.0, ge=0.0,
        description="Maximum seconds between AI decisions",
    )


class SimulatorConfig(BaseModel):
    """Top-level configuration for the Developer Activity Simulator.

    All configurable parameters from the TRD are captured here.
    """

    # Core settings
    duration_minutes: int = Field(
        default=60, ge=1, description="Total execution duration in minutes"
    )

    # Activity toggles
    mouse_enabled: bool = True
    keyboard_enabled: bool = True
    vscode_enabled: bool = True

    # Activity parameters
    idle_probability: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Probability of idle period between actions"
    )
    typing_speed_wpm: int = Field(
        default=50, ge=10, le=200, description="Typing speed in words per minute"
    )
    mouse_move_interval: float = Field(
        default=3.0, ge=0.5, le=30.0, description="Average seconds between mouse movements"
    )

    # Reproducibility
    random_seed: Optional[int] = Field(
        default=12345, description="Random seed for deterministic runs (null for random)"
    )

    # Scenario selection
    scenario: ScenarioType = ScenarioType.RANDOMIZED

    # Logging
    logging_verbosity: LogLevel = LogLevel.INFO

    # Reporting
    report_formats: list[ReportFormat] = Field(
        default_factory=lambda: [ReportFormat.JSON, ReportFormat.CSV, ReportFormat.HTML]
    )
    report_dir: str = "./reports"
    log_dir: str = "./logs"

    # Target applications
    target_applications: list[str] = Field(
        default_factory=lambda: ["Visual Studio Code", "Windows Terminal", "Google Chrome"]
    )

    # Sub-configs
    vscode: VSCodeConfig = Field(default_factory=VSCodeConfig)
    edge_timeout: EdgeTimeoutConfig = Field(default_factory=EdgeTimeoutConfig)
    intermittent: IntermittentConfig = Field(default_factory=IntermittentConfig)
    ai: AIConfig = Field(default_factory=AIConfig)

    @property
    def duration_seconds(self) -> float:
        """Total execution duration in seconds."""
        return self.duration_minutes * 60.0

    @property
    def is_windows(self) -> bool:
        """Check if running on Windows."""
        return sys.platform == "win32"

    @classmethod
    def from_yaml(cls, path: str | Path) -> SimulatorConfig:
        """Load configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            Validated SimulatorConfig instance.

        Raises:
            FileNotFoundError: If the config file does not exist.
            ValueError: If the config file contains invalid values.
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if raw is None:
            raw = {}

        return cls(**raw)

    def apply_overrides(self, **kwargs) -> SimulatorConfig:
        """Create a new config with overrides applied.

        Only non-None values in kwargs will override existing values.

        Args:
            **kwargs: Override values for config fields.

        Returns:
            New SimulatorConfig with overrides applied.
        """
        data = self.model_dump()
        for key, value in kwargs.items():
            if value is not None:
                # Shallow-merge dicts so partial sub-config overrides work
                # (e.g., ai={"api_key": "..."} merges into existing AIConfig)
                if isinstance(value, dict) and isinstance(data.get(key), dict):
                    data[key] = {**data[key], **value}
                else:
                    data[key] = value
        return SimulatorConfig(**data)
