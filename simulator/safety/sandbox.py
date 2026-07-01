"""Sandbox File Manager — isolates file operations to a safe directory.

Ensures the VS Code adapter operates only within a dedicated sandbox,
preventing accidental modifications to the user's real project files.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig

logger = logging.getLogger(__name__)

# Pre-populated files for the sandbox to make it look like a real project
_SANDBOX_FILES = {
    "main.py": (
        "def main():\n"
        "    print('Hello from the sandbox!')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    ),
    "utils.py": (
        "def add(a, b):\n"
        "    return a + b\n\n"
        "def subtract(a, b):\n"
        "    return a - b\n"
    ),
    "README.md": (
        "# Sandbox Project\n\n"
        "This is a temporary project used for activity simulation.\n"
        "Feel free to safely edit or delete these files.\n"
    ),
    "config.yaml": (
        "project:\n"
        "  name: sandbox\n"
        "  version: 1.0.0\n"
    ),
    "app.js": (
        "function startApp() {\n"
        "    console.log('App started');\n"
        "}\n"
    ),
}


class SandboxManager:
    """Manages an isolated workspace directory for file operations."""

    def __init__(self, config: SimulatorConfig) -> None:
        """Initialize the sandbox manager.

        Args:
            config: Simulator configuration.
        """
        self.config = config
        self._safety = config.safety
        self.sandbox_dir = Path(self._safety.sandbox_dir).resolve()

    @property
    def workspace_path(self) -> str:
        """The absolute path to the sandbox workspace."""
        return str(self.sandbox_dir)

    def setup(self) -> None:
        """Create the sandbox directory and pre-populate safe files."""
        if not self._safety.sandbox_enabled:
            return

        logger.info("Setting up sandbox at: %s", self.sandbox_dir)

        # Create directory if it doesn't exist
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Pre-populate files
        for filename, content in _SANDBOX_FILES.items():
            filepath = self.sandbox_dir / filename
            if not filepath.exists():
                try:
                    filepath.write_text(content, encoding="utf-8")
                except Exception as e:
                    logger.debug("Failed to write sandbox file %s: %s", filename, e)

        logger.debug("Sandbox pre-populated with %d files", len(_SANDBOX_FILES))

    def cleanup(self) -> None:
        """Remove the sandbox directory and all its contents if configured."""
        if not self._safety.sandbox_enabled or not self._safety.clean_on_exit:
            return

        if self.sandbox_dir.exists():
            try:
                shutil.rmtree(self.sandbox_dir)
                logger.info("Sandbox cleaned up: %s", self.sandbox_dir)
            except Exception as e:
                logger.error("Failed to clean up sandbox %s: %s", self.sandbox_dir, e)
