import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_window_guard(request):
    """Disable WindowGuard blocking globally in tests unless testing it specifically."""
    if "test_window_guard" in request.module.__name__:
        yield
        return
        
    with patch("simulator.safety.window_guard.WindowGuard.is_safe_to_act", return_value=True), \
         patch("simulator.safety.window_guard.WindowGuard.wait_for_safe_window", return_value=True):
        yield
