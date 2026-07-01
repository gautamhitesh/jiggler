"""Tests for the Sandbox Manager."""

from __future__ import annotations

from pathlib import Path

import pytest

from simulator.config import SimulatorConfig
from simulator.safety.sandbox import SandboxManager, _SANDBOX_FILES


@pytest.fixture
def sandbox_config(tmp_path):
    """Config configured to use a tmp directory for the sandbox."""
    return SimulatorConfig().apply_overrides(
        safety={"sandbox_dir": str(tmp_path / ".jiggler_sandbox"), "sandbox_enabled": True}
    )


class TestSandboxManager:
    """Tests for the SandboxManager."""

    def test_setup_creates_directory_and_files(self, sandbox_config):
        manager = SandboxManager(sandbox_config)
        sandbox_path = Path(manager.workspace_path)
        
        assert not sandbox_path.exists()
        manager.setup()
        
        assert sandbox_path.exists()
        assert sandbox_path.is_dir()
        
        for filename, content in _SANDBOX_FILES.items():
            file_path = sandbox_path / filename
            assert file_path.exists()
            assert file_path.read_text(encoding="utf-8") == content

    def test_setup_does_nothing_if_disabled(self, sandbox_config):
        sandbox_config.safety.sandbox_enabled = False
        manager = SandboxManager(sandbox_config)
        manager.setup()
        
        assert not Path(manager.workspace_path).exists()

    def test_cleanup_removes_directory_if_configured(self, sandbox_config):
        sandbox_config.safety.clean_on_exit = True
        manager = SandboxManager(sandbox_config)
        manager.setup()
        
        assert Path(manager.workspace_path).exists()
        manager.cleanup()
        assert not Path(manager.workspace_path).exists()

    def test_cleanup_does_nothing_if_not_configured(self, sandbox_config):
        sandbox_config.safety.clean_on_exit = False
        manager = SandboxManager(sandbox_config)
        manager.setup()
        
        assert Path(manager.workspace_path).exists()
        manager.cleanup()
        assert Path(manager.workspace_path).exists()

    def test_workspace_path_is_absolute(self, sandbox_config):
        manager = SandboxManager(sandbox_config)
        assert Path(manager.workspace_path).is_absolute()
