"""Root backwards-compatibility wrapper for end-to-end flow tests."""
import unittest
from tests.e2e.test_e2e_antigravity_flow import TestEndToEndAntigravityFlow

__all__ = ["TestEndToEndAntigravityFlow"]

if __name__ == "__main__":
    unittest.main()
