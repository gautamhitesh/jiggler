"""Tests for the configuration module."""

from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from simulator.config import (
    EdgeTimeoutConfig,
    IntermittentConfig,
    LogLevel,
    ReportFormat,
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
