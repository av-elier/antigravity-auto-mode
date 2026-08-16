"""Root backwards-compatibility wrapper for hook client tests."""
import unittest
from tests.integration.test_hook_client import TestHookClient

__all__ = ["TestHookClient"]

if __name__ == "__main__":
    unittest.main()
