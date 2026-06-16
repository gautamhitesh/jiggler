"""Tests for the reporter module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from simulator.config import ReportFormat, SimulatorConfig
from simulator.reporting.reporter import Reporter


# Sample JSONL log content for testing
SAMPLE_LOG_EVENTS = [
    {
        "timestamp": "2026-06-16T12:00:00Z",
        "event_type": "session",
        "action": "start",
        "application": "",
        "success": True,
        "details": {
            "session_id": "test_session",
            "config": {"duration_minutes": 5, "scenario": "randomized"},
        },
    },
    {
        "timestamp": "2026-06-16T12:00:01Z",
        "event_type": "mouse_move",
        "action": "move_realistic",
        "application": "",
        "success": True,
    },
    {
        "timestamp": "2026-06-16T12:00:03Z",
        "event_type": "keyboard_type",
        "action": "type_text",
        "application": "",
        "success": True,
    },
    {
        "timestamp": "2026-06-16T12:00:05Z",
        "event_type": "mouse_click",
        "action": "click_left",
        "application": "",
        "success": True,
    },
    {
        "timestamp": "2026-06-16T12:00:07Z",
        "event_type": "vscode_file",
        "action": "open_file",
        "application": "VS Code",
        "success": True,
    },
    {
        "timestamp": "2026-06-16T12:00:09Z",
        "event_type": "keyboard_type",
        "action": "type_code_snippet",
        "application": "",
        "success": False,
        "error_message": "Test error for validation",
    },
    {
        "timestamp": "2026-06-16T12:00:10Z",
        "event_type": "mouse_idle",
        "action": "idle",
        "application": "",
        "success": True,
        "details": {"duration_seconds": 3.5},
    },
    {
        "timestamp": "2026-06-16T12:00:15Z",
        "event_type": "session",
        "action": "end",
        "application": "",
        "success": True,
        "details": {
            "session_id": "test_session",
            "reason": "completed",
            "total_events": 5,
            "total_errors": 1,
            "runtime_seconds": 15.0,
        },
    },
]


class TestReporter:
    """Tests for the Reporter class."""

    @pytest.fixture
    def config(self, tmp_path):
        """Create a test configuration with temp directories."""
        return SimulatorConfig(
            report_dir=str(tmp_path / "reports"),
            log_dir=str(tmp_path / "logs"),
            report_formats=[ReportFormat.JSON, ReportFormat.CSV, ReportFormat.HTML],
        )

    @pytest.fixture
    def reporter(self, config):
        """Create a reporter instance."""
        return Reporter(config)

    @pytest.fixture
    def log_file(self, tmp_path) -> Path:
        """Create a sample JSONL log file."""
        log_path = tmp_path / "test_session.jsonl"
        with open(log_path, "w", encoding="utf-8") as f:
            for event in SAMPLE_LOG_EVENTS:
                f.write(json.dumps(event) + "\n")
        return log_path

    def test_parse_log_file(self, reporter, log_file):
        """Test JSONL log file parsing."""
        events = reporter._parse_log_file(log_file)
        assert len(events) == len(SAMPLE_LOG_EVENTS)
        assert events[0]["event_type"] == "session"

    def test_compute_statistics(self, reporter, log_file):
        """Test aggregate statistics computation."""
        events = reporter._parse_log_file(log_file)
        import pandas as pd

        df = pd.DataFrame(events)
        stats = reporter._compute_statistics(df, events)

        assert stats["total_runtime_seconds"] == 15.0
        assert stats["session_id"] == "test_session"
        # 5 activity events (excluding 2 session events)
        assert stats["total_events"] > 0
        assert stats["failed_events"] >= 1
        assert stats["idle_duration_seconds"] == 3.5

    def test_generate_json_report(self, reporter, log_file):
        """Test JSON report generation."""
        output_files = reporter.generate_reports(
            log_file, "test_session", formats=[ReportFormat.JSON]
        )

        assert "json" in output_files
        json_path = output_files["json"]
        assert json_path.exists()

        with open(json_path) as f:
            report = json.load(f)

        assert "total_runtime_seconds" in report
        assert "activity_counts" in report
        assert "total_events" in report

    def test_generate_csv_report(self, reporter, log_file):
        """Test CSV report generation."""
        output_files = reporter.generate_reports(
            log_file, "test_session", formats=[ReportFormat.CSV]
        )

        assert "csv" in output_files
        csv_path = output_files["csv"]
        assert csv_path.exists()

        import pandas as pd

        df = pd.read_csv(csv_path)
        assert len(df) > 0
        assert "metric" in df.columns
        assert "value" in df.columns

    def test_generate_html_report(self, reporter, log_file):
        """Test HTML report generation."""
        output_files = reporter.generate_reports(
            log_file, "test_session", formats=[ReportFormat.HTML]
        )

        assert "html" in output_files
        html_path = output_files["html"]
        assert html_path.exists()

        content = html_path.read_text(encoding="utf-8")
        assert "Developer Activity Simulator" in content
        assert "TEST HARNESS" in content
        assert "test_session" in content

    def test_generate_all_formats(self, reporter, log_file):
        """Test generating all report formats at once."""
        output_files = reporter.generate_reports(log_file, "test_session")

        assert "json" in output_files
        assert "csv" in output_files
        assert "html" in output_files

        for fmt, path in output_files.items():
            assert path.exists(), f"{fmt} report file should exist"

    def test_format_duration(self):
        """Test duration formatting helper."""
        assert Reporter._format_duration(0) == "0s"
        assert Reporter._format_duration(30) == "30s"
        assert Reporter._format_duration(90) == "1m 30s"
        assert Reporter._format_duration(3661) == "1h 1m 1s"
        assert Reporter._format_duration(7200) == "2h 0s"

    def test_empty_log_file(self, reporter, tmp_path):
        """Test handling of empty log file."""
        empty_log = tmp_path / "empty.jsonl"
        empty_log.write_text("")

        output_files = reporter.generate_reports(empty_log, "empty_session")
        assert output_files == {}
