"""Developer Activity Simulator — CLI Entry Point.

Usage:
    python main.py                          # Run with default config
    python main.py --config my_config.yaml  # Custom config file
    python main.py --scenario continuous    # Override scenario
    python main.py --duration 5 --dry-run   # Quick dry-run test
    python main.py --help                   # Show all options
"""

from __future__ import annotations

import argparse
import sys

from simulator import __tool_name__, __version__
from simulator.config import ScenarioType, SimulatorConfig
from simulator.controller import Controller


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        prog="jiggler",
        description=f"{__tool_name__} v{__version__} — "
        "A configurable testing tool that simulates workstation activity "
        "for QA validation of developer monitoring systems.",
        epilog=(
            "NOTICE: This tool is intended solely for QA, testing, "
            "benchmarking, and validation purposes in controlled environments. "
            "It must not be used to bypass, deceive, or falsify employee "
            "productivity monitoring."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "--scenario",
        type=str,
        choices=[s.value for s in ScenarioType],
        default=None,
        help="Override the test scenario (default: from config)",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Override duration in minutes (default: from config)",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override random seed for deterministic runs (default: from config)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions without executing them (no actual input events)",
    )

    parser.add_argument(
        "--report-dir",
        type=str,
        default=None,
        help="Override report output directory (default: from config)",
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Override log output directory (default: from config)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging verbosity",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point for the Developer Activity Simulator.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args()

    # Load configuration
    try:
        config = SimulatorConfig.from_yaml(args.config)
    except FileNotFoundError:
        print(f"Configuration file not found: {args.config}", file=sys.stderr)
        print("Creating default config and continuing...", file=sys.stderr)
        config = SimulatorConfig()
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    # Apply CLI overrides
    overrides = {}
    if args.scenario is not None:
        overrides["scenario"] = args.scenario
    if args.duration is not None:
        overrides["duration_minutes"] = args.duration
    if args.seed is not None:
        overrides["random_seed"] = args.seed
    if args.report_dir is not None:
        overrides["report_dir"] = args.report_dir
    if args.log_dir is not None:
        overrides["log_dir"] = args.log_dir
    if args.verbose:
        overrides["logging_verbosity"] = "DEBUG"

    if overrides:
        config = config.apply_overrides(**overrides)

    # Create and run controller
    controller = Controller(config=config, dry_run=args.dry_run)

    try:
        controller.run()
        return 0
    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
