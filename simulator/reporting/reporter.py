"""Report generator for the Developer Activity Simulator.

Reads JSONL log files and produces summary reports in JSON, CSV,
and HTML formats with aggregate statistics and charts.
"""

from __future__ import annotations

import base64
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from simulator.config import ReportFormat, SimulatorConfig


class Reporter:
    """Generates post-run reports from session log files.

    Reads the structured JSONL log file, aggregates statistics,
    and produces reports in the configured output formats.
    """

    def __init__(self, config: SimulatorConfig) -> None:
        """Initialize the reporter.

        Args:
            config: Simulator configuration.
        """
        self.config = config
        self.report_dir = Path(config.report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # Set up Jinja2 template environment
        template_dir = Path(__file__).parent / "templates"
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )

    def generate_reports(
        self,
        log_file_path: Path,
        session_id: str,
        formats: list[ReportFormat] | None = None,
    ) -> dict[str, Path]:
        """Generate reports from a session log file.

        Args:
            log_file_path: Path to the JSONL log file.
            session_id: Session identifier for naming reports.
            formats: Report formats to generate. Defaults to config value.

        Returns:
            Dictionary mapping format name to output file path.
        """
        if formats is None:
            formats = self.config.report_formats

        # Parse log file
        events = self._parse_log_file(log_file_path)
        if not events:
            return {}

        # Create DataFrame for analysis
        df = pd.DataFrame(events)

        # Compute aggregate statistics
        stats = self._compute_statistics(df, events)

        # Generate each requested format
        output_files: dict[str, Path] = {}

        for fmt in formats:
            if fmt == ReportFormat.JSON:
                path = self._generate_json_report(stats, session_id)
                output_files["json"] = path
            elif fmt == ReportFormat.CSV:
                path = self._generate_csv_report(df, stats, session_id)
                output_files["csv"] = path
            elif fmt == ReportFormat.HTML:
                path = self._generate_html_report(df, stats, session_id)
                output_files["html"] = path

        return output_files

    def _parse_log_file(self, log_file_path: Path) -> list[dict[str, Any]]:
        """Parse a JSONL log file into a list of event dictionaries.

        Args:
            log_file_path: Path to the .jsonl file.

        Returns:
            List of event dictionaries.
        """
        events = []
        with open(log_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events

    def _compute_statistics(
        self, df: pd.DataFrame, events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Compute aggregate statistics from event data.

        Args:
            df: DataFrame of events.
            events: Raw event list.

        Returns:
            Dictionary of computed statistics.
        """
        # Find session start/end events
        session_events = [e for e in events if e.get("event_type") == "session"]
        start_event = next(
            (e for e in session_events if e.get("action") == "start"), None
        )
        end_event = next(
            (e for e in session_events if e.get("action") == "end"), None
        )

        # Filter out session events for activity analysis
        activity_df = df[df["event_type"] != "session"].copy()

        # Total runtime
        total_runtime = 0.0
        if end_event and "details" in end_event:
            total_runtime = end_event["details"].get("runtime_seconds", 0)
        elif len(events) >= 2:
            try:
                start_time = datetime.fromisoformat(events[0]["timestamp"])
                end_time = datetime.fromisoformat(events[-1]["timestamp"])
                total_runtime = (end_time - start_time).total_seconds()
            except (ValueError, KeyError):
                pass

        # Activity counts by event type
        activity_counts = {}
        if not activity_df.empty and "event_type" in activity_df.columns:
            activity_counts = activity_df["event_type"].value_counts().to_dict()

        # Action counts
        action_counts = {}
        if not activity_df.empty and "action" in activity_df.columns:
            action_counts = activity_df["action"].value_counts().to_dict()

        # Success/failure counts
        total_events = len(activity_df)
        success_count = 0
        failure_count = 0
        if not activity_df.empty and "success" in activity_df.columns:
            success_count = int(activity_df["success"].sum())
            failure_count = total_events - success_count

        # Error events
        error_events = []
        if not activity_df.empty and "success" in activity_df.columns:
            error_df = activity_df[activity_df["success"] == False]
            error_events = error_df.to_dict("records")

        # Idle duration tracking
        idle_duration = 0.0
        for e in events:
            if e.get("event_type") in ("mouse_idle",) or e.get("action", "").startswith("idle"):
                details = e.get("details", {})
                idle_duration += details.get("duration_seconds", 0)

        # Application involvement
        app_counts = {}
        if not activity_df.empty and "application" in activity_df.columns:
            app_series = activity_df["application"].replace("", pd.NA).dropna()
            if not app_series.empty:
                app_counts = app_series.value_counts().to_dict()

        stats = {
            "session_id": end_event["details"]["session_id"] if end_event and "details" in end_event else "unknown",
            "total_runtime_seconds": round(total_runtime, 2),
            "total_runtime_formatted": self._format_duration(total_runtime),
            "total_events": total_events,
            "successful_events": success_count,
            "failed_events": failure_count,
            "activity_counts": activity_counts,
            "action_counts": action_counts,
            "idle_duration_seconds": round(idle_duration, 2),
            "error_events": error_events[:50],  # Cap at 50 for report readability
            "total_errors": len(error_events),
            "application_counts": app_counts,
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Add config summary if available
        if start_event and "details" in start_event:
            stats["config"] = start_event["details"].get("config", {})

        return stats

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into a human-readable duration string.

        Args:
            seconds: Duration in seconds.

        Returns:
            Formatted string like "1h 23m 45s".
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")

        return " ".join(parts)

    def _generate_json_report(
        self, stats: dict[str, Any], session_id: str
    ) -> Path:
        """Generate a JSON summary report.

        Args:
            stats: Computed statistics.
            session_id: Session identifier.

        Returns:
            Path to the generated JSON file.
        """
        output_path = self.report_dir / f"report_{session_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, default=str)
        return output_path

    def _generate_csv_report(
        self, df: pd.DataFrame, stats: dict[str, Any], session_id: str
    ) -> Path:
        """Generate a CSV tabular report.

        Creates two CSV files:
        - Summary statistics
        - Raw event data

        Args:
            df: DataFrame of all events.
            stats: Computed statistics.
            session_id: Session identifier.

        Returns:
            Path to the summary CSV file.
        """
        # Summary CSV
        summary_path = self.report_dir / f"report_{session_id}_summary.csv"
        summary_rows = [
            {"metric": "Total Runtime", "value": stats["total_runtime_formatted"]},
            {"metric": "Total Events", "value": stats["total_events"]},
            {"metric": "Successful Events", "value": stats["successful_events"]},
            {"metric": "Failed Events", "value": stats["failed_events"]},
            {"metric": "Idle Duration (s)", "value": stats["idle_duration_seconds"]},
            {"metric": "Total Errors", "value": stats["total_errors"]},
        ]

        # Add activity counts
        for event_type, count in stats.get("activity_counts", {}).items():
            summary_rows.append({"metric": f"Count: {event_type}", "value": count})

        pd.DataFrame(summary_rows).to_csv(summary_path, index=False)

        # Raw events CSV
        events_path = self.report_dir / f"report_{session_id}_events.csv"
        activity_df = df[df["event_type"] != "session"].copy()
        if not activity_df.empty:
            # Flatten details column for CSV
            if "details" in activity_df.columns:
                activity_df = activity_df.drop(columns=["details"])
            activity_df.to_csv(events_path, index=False)

        return summary_path

    def _generate_html_report(
        self, df: pd.DataFrame, stats: dict[str, Any], session_id: str
    ) -> Path:
        """Generate an HTML report with charts and tables.

        Args:
            df: DataFrame of all events.
            stats: Computed statistics.
            session_id: Session identifier.

        Returns:
            Path to the generated HTML file.
        """
        # Generate chart images
        charts = self._generate_charts(df, stats)

        # Render HTML template
        template = self._jinja_env.get_template("report.html.j2")
        html_content = template.render(
            stats=stats,
            charts=charts,
            session_id=session_id,
        )

        output_path = self.report_dir / f"report_{session_id}.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path

    def _generate_charts(
        self, df: pd.DataFrame, stats: dict[str, Any]
    ) -> dict[str, str]:
        """Generate chart images as base64-encoded PNGs.

        Args:
            df: DataFrame of events.
            stats: Computed statistics.

        Returns:
            Dictionary of chart_name -> base64-encoded PNG string.
        """
        charts = {}

        try:
            import matplotlib

            matplotlib.use("Agg")  # Non-interactive backend
            import matplotlib.pyplot as plt

            # Activity type distribution pie chart
            activity_counts = stats.get("activity_counts", {})
            if activity_counts:
                fig, ax = plt.subplots(1, 1, figsize=(8, 5))
                labels = list(activity_counts.keys())
                values = list(activity_counts.values())

                colors = plt.cm.Set3(range(len(labels)))
                ax.pie(
                    values,
                    labels=labels,
                    autopct="%1.1f%%",
                    colors=colors,
                    startangle=90,
                )
                ax.set_title("Activity Distribution by Event Type")
                charts["activity_distribution"] = self._fig_to_base64(fig)
                plt.close(fig)

            # Action frequency bar chart
            action_counts = stats.get("action_counts", {})
            if action_counts:
                fig, ax = plt.subplots(1, 1, figsize=(12, 5))
                # Show top 15 actions
                sorted_actions = dict(
                    sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:15]
                )
                bars = ax.barh(
                    list(sorted_actions.keys()),
                    list(sorted_actions.values()),
                    color="#4a90d9",
                )
                ax.set_xlabel("Count")
                ax.set_title("Top Actions by Frequency")
                ax.invert_yaxis()
                plt.tight_layout()
                charts["action_frequency"] = self._fig_to_base64(fig)
                plt.close(fig)

            # Timeline of events (events per minute)
            activity_df = df[df["event_type"] != "session"].copy()
            if not activity_df.empty and "timestamp" in activity_df.columns:
                try:
                    activity_df["ts"] = pd.to_datetime(activity_df["timestamp"])
                    activity_df = activity_df.set_index("ts")
                    events_per_min = activity_df.resample("1min").size()

                    if len(events_per_min) > 1:
                        fig, ax = plt.subplots(1, 1, figsize=(12, 4))
                        ax.fill_between(
                            range(len(events_per_min)),
                            events_per_min.values,
                            alpha=0.4,
                            color="#4a90d9",
                        )
                        ax.plot(
                            range(len(events_per_min)),
                            events_per_min.values,
                            color="#2c5f8a",
                            linewidth=1.5,
                        )
                        ax.set_xlabel("Minutes Elapsed")
                        ax.set_ylabel("Events")
                        ax.set_title("Activity Timeline (Events per Minute)")
                        plt.tight_layout()
                        charts["timeline"] = self._fig_to_base64(fig)
                        plt.close(fig)
                except Exception:
                    pass

        except ImportError:
            # matplotlib not available — skip charts
            pass

        return charts

    @staticmethod
    def _fig_to_base64(fig) -> str:
        """Convert a matplotlib figure to a base64-encoded PNG string.

        Args:
            fig: Matplotlib figure object.

        Returns:
            Base64-encoded PNG string.
        """
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
