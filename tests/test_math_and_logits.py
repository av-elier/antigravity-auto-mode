"""Root backwards-compatibility wrapper for unit math and logits tests."""
import unittest
from tests.unit.test_math_and_logits import TestMathAndLogits

__all__ = ["TestMathAndLogits"]

if __name__ == "__main__":
    unittest.main()
