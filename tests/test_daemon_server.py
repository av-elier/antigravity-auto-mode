"""Root backwards-compatibility wrapper for daemon server tests."""
import unittest
from tests.integration.test_daemon_server import TestDaemonServer

__all__ = ["TestDaemonServer"]

if __name__ == "__main__":
    unittest.main()
