    """Sample Python module for VS Code adapter testing.

This file is used by the Developer Activity Simulator to test
VS Code interactions like opening files, editing, and saving.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TaskItem:
    """Represents a single task in the task tracker."""

    title: str
    description: str = ""
    priority: int = 0
    completed: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tags: list[str] = field(default_factory=list)

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.completed = True

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "completed": self.completed,
            "created_at": self.created_at,
            "tags": self.tags,
        }


class TaskTracker:
    """Simple task tracker for demonstration purposes."""

    def __init__(self) -> None:
        self._tasks: list[TaskItem] = []

    def add_task(self, title: str, **kwargs) -> TaskItem:
        """Add a new task to the tracker.

        Args:
            title: Task title.
            **kwargs: Additional task properties.

        Returns:
            The created TaskItem.
        """
        task = TaskItem(title=title, **kwargs)
        self._tasks.append(task)
        return task

    def get_pending(self) -> list[TaskItem]:
        """Get all incomplete tasks, sorted by priority (descending)."""
        return sorted(
            [t for t in self._tasks if not t.completed],
            key=lambda t: t.priority,
            reverse=True,
        )

    def get_completed(self) -> list[TaskItem]:
        """Get all completed tasks."""
        return [t for t in self._tasks if t.completed]

    def export_json(self) -> str:
        """Export all tasks as a JSON string."""
        return json.dumps(
            [t.to_dict() for t in self._tasks],
            indent=2,
        )

    @property
    def total_count(self) -> int:
        """Total number of tasks."""
        return len(self._tasks)

    @property
    def completion_rate(self) -> float:
        """Percentage of completed tasks (0.0 to 1.0)."""
        if not self._tasks:
            return 0.0
        return len(self.get_completed()) / len(self._tasks)


def fibonacci(n: int) -> list[int]:
    """Generate the first N Fibonacci numbers.

    Args:
        n: Number of Fibonacci values to generate.

    Returns:
        List of Fibonacci numbers.
    """
    if n <= 0:
        return []
    if n == 1:
        return [0]

    sequence = [0, 1]
    for _ in range(2, n):
        sequence.append(sequence[-1] + sequence[-2])
    return sequence


def main() -> None:
    """Demonstrate the task tracker and Fibonacci function."""
    tracker = TaskTracker()

    tracker.add_task("Set up development environment", priority=3, tags=["setup"])
    tracker.add_task("Write unit tests", priority=2, tags=["testing"])
    tracker.add_task("Update documentation", priority=1, tags=["docs"])
    tracker.add_task("Code review", priority=2, tags=["review"])

    print(f"Total tasks: {tracker.total_count}")
    print(f"Pending: {len(tracker.get_pending())}")
    print(f"Fibonacci(10): {fibonacci(10)}")


if __name__ == "__main__":
    main()
calculate_metrics(data: list[dict]) -> dict:
    """Calculate aggregate metrics from raw data entries."""
    total = sum(entry.get("value", 0) for entry in data)
    count = len(data)
    average = total / count if count > 0 else 0
    return {"total": total, "count": count, "average": round(average, 2)}
"""