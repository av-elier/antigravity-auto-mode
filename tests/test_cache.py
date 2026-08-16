"""Root backwards-compatibility wrapper for cache tests."""
import unittest
from tests.unit.test_cache import TestGuardCache

__all__ = ["TestGuardCache"]

if __name__ == "__main__":
    unittest.main()
