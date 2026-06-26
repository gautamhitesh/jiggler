"""Tests for the command-line interface overrides."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
import pytest

from main import parse_args


def test_cli_mouse_only():
    """Test that --mouse-only flag parses correctly."""
    with patch("sys.argv", ["main.py", "--mouse-only"]):
        args = parse_args()
        assert args.mouse_only is True
        assert args.keyboard_only is False
        assert args.vscode_only is False
        assert args.no_mouse is False


def test_cli_keyboard_only():
    """Test that --keyboard-only flag parses correctly."""
    with patch("sys.argv", ["main.py", "--keyboard-only"]):
        args = parse_args()
        assert args.mouse_only is False
        assert args.keyboard_only is True
        assert args.vscode_only is False
        assert args.no_keyboard is False


def test_cli_vscode_only():
    """Test that --vscode-only flag parses correctly."""
    with patch("sys.argv", ["main.py", "--vscode-only"]):
        args = parse_args()
        assert args.mouse_only is False
        assert args.keyboard_only is False
        assert args.vscode_only is True
        assert args.no_vscode is False


def test_cli_disable_flags():
    """Test individual disable flags."""
    with patch("sys.argv", ["main.py", "--no-mouse", "--no-keyboard", "--no-vscode"]):
        args = parse_args()
        assert args.no_mouse is True
        assert args.no_keyboard is True
        assert args.no_vscode is True


@patch("main.Controller")
def test_main_cli_overrides(mock_controller_class):
    """Test that main() correctly applies cli overrides to the Controller config."""
    mock_controller = MagicMock()
    mock_controller_class.return_value = mock_controller

    with patch("sys.argv", ["main.py", "--mouse-only", "--duration", "5"]):
        from main import main
        exit_code = main()
        assert exit_code == 0

        # Verify Controller was instantiated with overrides applied
        mock_controller_class.assert_called_once()
        _, kwargs = mock_controller_class.call_args
        config = kwargs.get("config")
        assert config is not None
        assert config.mouse_enabled is True
        assert config.keyboard_enabled is False
        assert config.vscode_enabled is False
        assert config.duration_minutes == 5
