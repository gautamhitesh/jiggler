"""VS Code adapter for the Developer Activity Simulator.

Handles VS Code-specific interactions including launching, opening files,
creating new files, switching tabs, scrolling, and saving.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pyautogui

from simulator.generators.base import ActivityEvent, BaseGenerator

if TYPE_CHECKING:
    from simulator.config import SimulatorConfig
    from simulator.logging.event_logger import EventLogger


class VSCodeAdapter(BaseGenerator):
    """Adapter for VS Code interactions.

    Uses keyboard shortcuts to interact with VS Code in a way that
    mimics real developer behavior. Supports launching VS Code,
    opening/creating files, tab switching, scrolling, and saving.
    """

    ACTIONS = [
        "launch",
        "open_file",
        "create_new_file",
        "switch_tab",
        "scroll_down",
        "scroll_up",
        "save_file",
        "toggle_terminal",
        "go_to_line",
        "find_text",
        "close_tab",
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        
        # Use sandbox if enabled, otherwise use configured workspace
        if self.config.safety.sandbox_enabled:
            self._workspace_path = Path(self.config.safety.sandbox_dir).resolve()
        else:
            self._workspace_path = Path(self.config.vscode.workspace_path).resolve()
            
        self._launched = False
        self._open_files: list[str] = []

        # Discover existing files in workspace
        self._workspace_files: list[str] = []
        if self._workspace_path.exists():
            self._workspace_files = [
                str(f.relative_to(self._workspace_path))
                for f in self._workspace_path.rglob("*")
                if f.is_file() and not f.name.startswith(".")
            ]

    @property
    def generator_type(self) -> str:
        return "vscode"

    def get_available_actions(self) -> list[str]:
        return list(self.ACTIONS)

    def is_available(self) -> bool:
        """Check if VS Code (code command) is available."""
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["where", "code"],
                    capture_output=True, text=True, timeout=5
                )
            else:
                result = subprocess.run(
                    ["which", "code"],
                    capture_output=True, text=True, timeout=5
                )
            return result.returncode == 0
        except Exception:
            return False

    def _execute_action(self, action_name: str) -> ActivityEvent:
        method = getattr(self, f"_action_{action_name}", None)
        if method is None:
            raise ValueError(f"Unknown VS Code action: {action_name}")
        return method()

    def _action_launch(self) -> ActivityEvent:
        """Launch VS Code with the test workspace folder."""
        workspace = str(self._workspace_path)

        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    ["code", workspace],
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["code", workspace],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            # Wait for VS Code to start
            time.sleep(3.0)
            self._launched = True

            return ActivityEvent(
                event_type="vscode_launch",
                action="launch",
                application="VS Code",
                details={"workspace": workspace},
            )
        except FileNotFoundError:
            return ActivityEvent(
                event_type="vscode_launch",
                action="launch",
                application="VS Code",
                success=False,
                error_message="VS Code 'code' command not found in PATH",
            )

    def _action_open_file(self) -> ActivityEvent:
        """Open a file using VS Code's Quick Open (Ctrl+P)."""
        if not self._workspace_files:
            return ActivityEvent(
                event_type="vscode_file",
                action="open_file",
                application="VS Code",
                success=False,
                error_message="No files available in workspace",
            )

        filename = self.rng.choice(self._workspace_files)

        # Use Ctrl+P Quick Open
        pyautogui.hotkey("ctrl", "p")
        time.sleep(0.5)
        pyautogui.typewrite(filename, interval=0.05)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.5)

        if filename not in self._open_files:
            self._open_files.append(filename)

        return ActivityEvent(
            event_type="vscode_file",
            action="open_file",
            application="VS Code",
            details={"file": filename},
        )

    def _action_create_new_file(self) -> ActivityEvent:
        """Create a new file in VS Code using Ctrl+N."""
        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.5)

        # Type some placeholder content
        content = f"# New file created at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        pyautogui.typewrite(content, interval=0.03)
        time.sleep(0.3)

        return ActivityEvent(
            event_type="vscode_file",
            action="create_new_file",
            application="VS Code",
            details={"content_preview": content.strip()},
        )

    def _action_switch_tab(self) -> ActivityEvent:
        """Switch between open editor tabs."""
        # Randomly choose between next tab and previous tab
        if self.rng.random() > 0.5:
            pyautogui.hotkey("ctrl", "pagedown")
            direction = "next"
        else:
            pyautogui.hotkey("ctrl", "pageup")
            direction = "previous"

        time.sleep(0.3)

        return ActivityEvent(
            event_type="vscode_navigate",
            action="switch_tab",
            application="VS Code",
            details={"direction": direction},
        )

    def _action_scroll_down(self) -> ActivityEvent:
        """Scroll down in the current editor."""
        lines = self.rng.randint(3, 20)

        for _ in range(lines):
            pyautogui.press("down")
            time.sleep(0.05)

        return ActivityEvent(
            event_type="vscode_scroll",
            action="scroll_down",
            application="VS Code",
            details={"lines": lines},
        )

    def _action_scroll_up(self) -> ActivityEvent:
        """Scroll up in the current editor."""
        lines = self.rng.randint(3, 20)

        for _ in range(lines):
            pyautogui.press("up")
            time.sleep(0.05)

        return ActivityEvent(
            event_type="vscode_scroll",
            action="scroll_up",
            application="VS Code",
            details={"lines": lines},
        )

    def _action_save_file(self) -> ActivityEvent:
        """Save the current file using Ctrl+S."""
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.3)

        return ActivityEvent(
            event_type="vscode_file",
            action="save_file",
            application="VS Code",
        )

    def _action_toggle_terminal(self) -> ActivityEvent:
        """Toggle the integrated terminal with Ctrl+`."""
        pyautogui.hotkey("ctrl", "`")
        time.sleep(0.5)

        return ActivityEvent(
            event_type="vscode_navigate",
            action="toggle_terminal",
            application="VS Code",
        )

    def _action_go_to_line(self) -> ActivityEvent:
        """Go to a random line number using Ctrl+G."""
        line_number = self.rng.randint(1, 100)

        pyautogui.hotkey("ctrl", "g")
        time.sleep(0.3)
        pyautogui.typewrite(str(line_number), interval=0.05)
        pyautogui.press("enter")
        time.sleep(0.3)

        return ActivityEvent(
            event_type="vscode_navigate",
            action="go_to_line",
            application="VS Code",
            details={"line": line_number},
        )

    def _action_find_text(self) -> ActivityEvent:
        """Open Find dialog and search for a random term."""
        search_terms = ["def ", "class ", "import ", "return ", "if ", "for ", "TODO", "FIXME"]
        term = self.rng.choice(search_terms)

        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)
        pyautogui.typewrite(term, interval=0.05)
        time.sleep(0.5)
        pyautogui.press("escape")
        time.sleep(0.2)

        return ActivityEvent(
            event_type="vscode_navigate",
            action="find_text",
            application="VS Code",
            details={"search_term": term},
        )

    def _action_close_tab(self) -> ActivityEvent:
        """Close the current editor tab with Ctrl+W."""
        pyautogui.hotkey("ctrl", "w")
        time.sleep(0.3)

        return ActivityEvent(
            event_type="vscode_file",
            action="close_tab",
            application="VS Code",
        )
