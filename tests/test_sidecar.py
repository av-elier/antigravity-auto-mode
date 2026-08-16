"""Root backwards-compatibility wrapper for sidecar integration tests."""
import unittest
from tests.integration.test_sidecar import TestSidecarIntegration

__all__ = ["TestSidecarIntegration"]

if __name__ == "__main__":
    unittest.main()
