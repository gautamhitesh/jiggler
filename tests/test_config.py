"""Tests for the configuration module."""

from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from simulator.config import (
    AIConfig,
    EdgeTimeoutConfig,
    IntermittentConfig,
    LogLevel,
    ReportFormat,
    SafetyConfig,
    ScenarioType,
    SimulatorConfig,
    VSCodeConfig,
)


class TestSimulatorConfig:
    """Tests for SimulatorConfig validation and loading."""

    def test_default_config(self):
        """Test that default config is valid."""
        config = SimulatorConfig()
        assert config.duration_minutes == 60
        assert config.mouse_enabled is True
        assert config.keyboard_enabled is True
        assert config.vscode_enabled is True
        assert config.idle_probability == 0.25
        assert config.typing_speed_wpm == 50
        assert config.random_seed == 12345
        assert config.scenario == ScenarioType.RANDOMIZED

    def test_duration_seconds_property(self):
        """Test the duration_seconds computed property."""
        config = SimulatorConfig(duration_minutes=10)
        assert config.duration_seconds == 600.0

    def test_duration_must_be_positive(self):
        """Test that duration_minutes must be >= 1."""
        with pytest.raises(Exception):
            SimulatorConfig(duration_minutes=0)

    def test_idle_probability_bounds(self):
        """Test that idle_probability must be between 0 and 1."""
        config = SimulatorConfig(idle_probability=0.0)
        assert config.idle_probability == 0.0

        config = SimulatorConfig(idle_probability=1.0)
        assert config.idle_probability == 1.0

        with pytest.raises(Exception):
            SimulatorConfig(idle_probability=-0.1)

        with pytest.raises(Exception):
            SimulatorConfig(idle_probability=1.1)

    def test_typing_speed_bounds(self):
        """Test that typing_speed_wpm must be in [10, 200]."""
        config = SimulatorConfig(typing_speed_wpm=10)
        assert config.typing_speed_wpm == 10

        config = SimulatorConfig(typing_speed_wpm=200)
        assert config.typing_speed_wpm == 200

        with pytest.raises(Exception):
            SimulatorConfig(typing_speed_wpm=5)

        with pytest.raises(Exception):
            SimulatorConfig(typing_speed_wpm=201)

    def test_scenario_types(self):
        """Test all scenario types are accepted."""
        for scenario in ScenarioType:
            config = SimulatorConfig(scenario=scenario)
            assert config.scenario == scenario

    def test_report_formats(self):
        """Test report format configuration."""
        config = SimulatorConfig(report_formats=[ReportFormat.JSON, ReportFormat.CSV])
        assert len(config.report_formats) == 2
        assert ReportFormat.JSON in config.report_formats
        assert ReportFormat.CSV in config.report_formats

    def test_from_yaml(self):
        """Test loading configuration from a YAML file."""
        yaml_content = {
            "duration_minutes": 30,
            "mouse_enabled": False,
            "scenario": "continuous",
            "typing_speed_wpm": 80,
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(yaml_content, f)
            temp_path = f.name

        try:
            config = SimulatorConfig.from_yaml(temp_path)
            assert config.duration_minutes == 30
            assert config.mouse_enabled is False
            assert config.scenario == ScenarioType.CONTINUOUS
            assert config.typing_speed_wpm == 80
            # Check defaults for unspecified fields
            assert config.keyboard_enabled is True
        finally:
            os.unlink(temp_path)

    def test_from_yaml_file_not_found(self):
        """Test error when YAML file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            SimulatorConfig.from_yaml("/nonexistent/path.yaml")

    def test_from_yaml_empty_file(self):
        """Test loading from an empty YAML file uses defaults."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("")
            temp_path = f.name

        try:
            config = SimulatorConfig.from_yaml(temp_path)
            assert config.duration_minutes == 60  # Default value
        finally:
            os.unlink(temp_path)

    def test_apply_overrides(self):
        """Test applying CLI overrides to config."""
        config = SimulatorConfig(duration_minutes=60, scenario=ScenarioType.RANDOMIZED)
        overridden = config.apply_overrides(
            duration_minutes=30,
            scenario="continuous",
        )
        assert overridden.duration_minutes == 30
        assert overridden.scenario == ScenarioType.CONTINUOUS
        # Original should be unchanged
        assert config.duration_minutes == 60

    def test_apply_overrides_none_ignored(self):
        """Test that None overrides are ignored."""
        config = SimulatorConfig(duration_minutes=60)
        overridden = config.apply_overrides(duration_minutes=None)
        assert overridden.duration_minutes == 60

    def test_apply_overrides_merges_dict_values(self):
        """Test that dict overrides are shallow-merged, not replaced."""
        config = SimulatorConfig(ai=AIConfig(api_key="original", model="test/model"))
        overridden = config.apply_overrides(ai={"api_key": "new-key"})
        assert overridden.ai.api_key == "new-key"
        assert overridden.ai.model == "test/model"  # Not wiped


class TestSubConfigs:
    """Tests for sub-configuration models."""

    def test_vscode_config_defaults(self):
        """Test VSCodeConfig default values."""
        cfg = VSCodeConfig()
        assert cfg.workspace_path == "./test_workspace"
        assert cfg.auto_save_interval == 30

    def test_vscode_config_min_interval(self):
        """Test VSCodeConfig auto_save_interval minimum."""
        with pytest.raises(Exception):
            VSCodeConfig(auto_save_interval=2)

    def test_edge_timeout_config_defaults(self):
        """Test EdgeTimeoutConfig default values."""
        cfg = EdgeTimeoutConfig()
        assert cfg.timeout_threshold_seconds == 300
        assert cfg.activity_delta_seconds == 10

    def test_intermittent_config_validation(self):
        """Test IntermittentConfig cross-field validation."""
        # Valid: max >= min
        cfg = IntermittentConfig(
            burst_duration_min=60,
            burst_duration_max=120,
            idle_duration_min=30,
            idle_duration_max=90,
        )
        assert cfg.burst_duration_min == 60
        assert cfg.burst_duration_max == 120

    def test_intermittent_config_invalid_burst_range(self):
        """Test that burst_duration_max < burst_duration_min raises error."""
        with pytest.raises(Exception):
            IntermittentConfig(
                burst_duration_min=200,
                burst_duration_max=100,
            )

    def test_intermittent_config_invalid_idle_range(self):
        """Test that idle_duration_max < idle_duration_min raises error."""
        with pytest.raises(Exception):
            IntermittentConfig(
                idle_duration_min=200,
                idle_duration_max=100,
            )


class TestAIConfig:
    """Tests for AIConfig validation."""

    def test_default_ai_config(self):
        """Test that default AIConfig is valid."""
        cfg = AIConfig()
        assert cfg.api_key is None
        assert cfg.model == "google/gemini-2.0-flash"
        assert cfg.base_url == "https://openrouter.ai/api/v1"
        assert cfg.temperature == 0.9
        assert cfg.context_window == 10
        assert cfg.max_api_calls == 500

    def test_ai_config_temperature_bounds(self):
        """Test that temperature must be in [0.0, 2.0]."""
        cfg = AIConfig(temperature=0.0)
        assert cfg.temperature == 0.0

        cfg = AIConfig(temperature=2.0)
        assert cfg.temperature == 2.0

        with pytest.raises(Exception):
            AIConfig(temperature=-0.1)

        with pytest.raises(Exception):
            AIConfig(temperature=2.1)

    def test_ai_config_context_window_bounds(self):
        """Test context_window must be in [1, 50]."""
        with pytest.raises(Exception):
            AIConfig(context_window=0)

        with pytest.raises(Exception):
            AIConfig(context_window=51)

    def test_ai_config_max_api_calls_must_be_positive(self):
        """Test max_api_calls must be >= 1."""
        with pytest.raises(Exception):
            AIConfig(max_api_calls=0)

    def test_ai_driven_scenario_type(self):
        """Test that AI_DRIVEN is a valid scenario type."""
        config = SimulatorConfig(scenario=ScenarioType.AI_DRIVEN)
        assert config.scenario == ScenarioType.AI_DRIVEN

    def test_ai_config_in_simulator_config(self):
        """Test that SimulatorConfig includes AIConfig."""
        config = SimulatorConfig()
        assert isinstance(config.ai, AIConfig)
        assert config.ai.model == "google/gemini-2.0-flash"

    def test_ai_config_from_yaml(self):
        """Test loading AI config from YAML."""
        yaml_content = {
            "scenario": "ai_driven",
            "ai": {
                "api_key": "test-key",
                "model": "anthropic/claude-sonnet-4",
                "temperature": 0.7,
                "max_api_calls": 100,
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(yaml_content, f)
            temp_path = f.name

        try:
            config = SimulatorConfig.from_yaml(temp_path)
            assert config.scenario == ScenarioType.AI_DRIVEN
            assert config.ai.api_key == "test-key"
            assert config.ai.model == "anthropic/claude-sonnet-4"
            assert config.ai.temperature == 0.7
            assert config.ai.max_api_calls == 100
        finally:
            os.unlink(temp_path)


class TestSafetyConfig:
    """Tests for SafetyConfig defaults and validation."""

    def test_default_safety_config(self):
        """Test default values for safety config."""
        cfg = SafetyConfig()
        assert cfg.window_guard_enabled is True
        assert cfg.refocus_on_mismatch is True
        assert cfg.window_guard_timeout == 30.0
        assert cfg.presence_detection_enabled is True
        assert cfg.resume_delay_seconds == 5.0
        assert cfg.sandbox_enabled is True
        assert cfg.clean_on_exit is False
        assert cfg.log_blocked_actions is True
        assert len(cfg.blocked_actions) == 0

    def test_safety_config_in_simulator_config(self):
        """Test that SimulatorConfig includes SafetyConfig."""
        config = SimulatorConfig()
        assert isinstance(config.safety, SafetyConfig)
        assert config.safety.window_guard_enabled is True

    def test_safety_config_from_yaml(self):
        """Test loading safety config from YAML."""
        yaml_content = {
            "safety": {
                "window_guard_enabled": False,
                "sandbox_dir": "/tmp/test_sandbox",
                "clean_on_exit": True,
                "blocked_actions": ["mouse__click_left"],
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            temp_path = f.name

        try:
            config = SimulatorConfig.from_yaml(temp_path)
            assert config.safety.window_guard_enabled is False
            assert config.safety.sandbox_dir == "/tmp/test_sandbox"
            assert config.safety.clean_on_exit is True
            assert "mouse__click_left" in config.safety.blocked_actions
        finally:
            os.unlink(temp_path)

