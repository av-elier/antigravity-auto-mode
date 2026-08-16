"""Root backwards-compatibility wrapper for policy and prompt template tests."""
import unittest
from tests.unit.test_policy_and_prompts import TestPolicyAndPrompts

__all__ = ["TestPolicyAndPrompts"]

if __name__ == "__main__":
    unittest.main()
