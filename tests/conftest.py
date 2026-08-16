"""Global pytest configuration and fixtures for Shieldstral Guardrail test suite."""
import os
import sys
import time
import pytest
from pathlib import Path

# Ensure project root is always in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Returns the absolute Path to the project root directory."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def mock_daemon_port() -> int:
    """Provides a dedicated dynamic ephemeral port for tests requiring a mock server."""
    from daemon.server import create_server
    server = create_server(host="127.0.0.1", port=0, mock=True)
    port = server.actual_port
    server.server_close()
    return port


@pytest.fixture(autouse=True)
def clean_env():
    """Ensures test environment variables are safely isolated and restored."""
    old_env = os.environ.copy()
    yield
    # Restore original environment
    os.environ.clear()
    os.environ.update(old_env)


def pytest_configure(config):
    """Registers custom markers and configures pytest environment."""
    config.addinivalue_line("markers", "unit: Unit tests for math, policy, and cache logic")
    config.addinivalue_line("markers", "integration: Integration tests for server and hook client")
    config.addinivalue_line("markers", "e2e: End-to-end simulation tests")
    config.addinivalue_line("markers", "evals: Benchmark dataset evals and prompt regression tests")
    config.addinivalue_line("markers", "real_model: Tests requiring real Shieldstral GGUF weights")
    config.addinivalue_line("markers", "cache: Caching performance and correctness tests")
    config.addinivalue_line("markers", "sidecar: Antigravity Sidecar lifecycle tests")
    config.addinivalue_line("markers", "slow: Tests with longer execution times")
