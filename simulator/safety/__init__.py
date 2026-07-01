"""Safety module for the Developer Activity Simulator.

Provides three safety systems:
- WindowGuard: Validates foreground window before actions
- PresenceDetector: Detects real user input and pauses
- SandboxManager: Isolates file operations to a sandbox directory
"""
