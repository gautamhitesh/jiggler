# Development Notes

## Project Overview

This workspace contains sample files for the Developer Activity Simulator
test harness. These files are opened, edited, and saved by the VS Code
adapter during simulation runs.

## File Index

| File        | Language   | Purpose                          |
|-------------|-----------|----------------------------------|
| sample.py   | Python    | Task tracker and utility functions |
| sample.js   | JavaScript| Event bus and data utilities      |
| notes.md    | Markdown  | This file — project notes        |

## Recent Changes

- **2026-06-16**: Initial workspace setup
- Added sample Python module with TaskTracker class
- Added sample JavaScript module with EventBus pattern
- Created project documentation

## TODO

- [ ] Add more code snippet templates
- [ ] Create sample configuration files
- [ ] Add test data files for import testing
- [ ] Benchmark typing simulation accuracy

## Architecture Notes

The simulator uses a **plugin-based architecture** where each activity
generator is independent and registered with the central controller.
This allows new generators to be added without modifying existing code.

### Generator Interface

All generators implement the `BaseGenerator` abstract class:

```python
class BaseGenerator(ABC):
    @abstractmethod
    def execute(self, action_name: str) -> ActivityEvent: ...

    @abstractmethod
    def get_available_actions(self) -> list[str]: ...
```

### Event Logging

Events are stored as **JSON Lines** format for efficient append-only
writes during long-duration test sessions.
