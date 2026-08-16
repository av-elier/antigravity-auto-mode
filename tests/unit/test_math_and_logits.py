"""Unit tests for token logprob extraction and mathematical normalization.

Tag: @pytest.mark.unit
Guarantees: Correct probability computation, fail-closed defaults, token stripping.
"""
import math
import unittest
import pytest
from daemon.engine import (
    compute_unsafe_probability,
    normalize_token,
    SAFE_TOKENS,
    UNSAFE_TOKENS,
)


@pytest.mark.unit
class TestMathAndLogits(unittest.TestCase):
    """Verifies the mathematical normalization and single-token classification logic."""

    def test_normalize_token_standardization(self):
        """Validates that token strings with whitespace/punctuation are cleanly normalized."""
        self.assertEqual(normalize_token(" Yes"), "yes")
        self.assertEqual(normalize_token("No."), "no")
        self.assertEqual(normalize_token("  TRUE!  "), "true")
        self.assertEqual(normalize_token("False,"), "false")
        self.assertEqual(normalize_token("safe;"), "safe")
        self.assertEqual(normalize_token("  unsafe? "), "unsafe")

    def test_pure_safe_logprobs(self):
        """Validates that dominant 'No' logprob produces P(Unsafe) < 0.05."""
        top_logprobs = {
            "No": -0.01,
            " No": -0.05,
            "Yes": -5.0,
            "other": -6.0
        }
        p_unsafe, p_safe_sum, p_unsafe_sum = compute_unsafe_probability(top_logprobs)
        self.assertLess(p_unsafe, 0.05)
        self.assertGreater(p_safe_sum, p_unsafe_sum)

    def test_pure_unsafe_logprobs(self):
        """Validates that dominant 'Yes' logprob produces P(Unsafe) > 0.95."""
        top_logprobs = {
            "Yes": -0.02,
            " Yes": -0.08,
            "No": -4.5,
            " No": -5.0
        }
        p_unsafe, p_safe_sum, p_unsafe_sum = compute_unsafe_probability(top_logprobs)
        self.assertGreater(p_unsafe, 0.95)
        self.assertGreater(p_unsafe_sum, p_safe_sum)

    def test_ambiguous_logprobs(self):
        """Validates that equal probability distribution returns ~0.50 probability."""
        top_logprobs = {
            "Yes": -0.693147,  # ln(0.5)
            "No": -0.693147    # ln(0.5)
        }
        p_unsafe, p_safe_sum, p_unsafe_sum = compute_unsafe_probability(top_logprobs)
        self.assertAlmostEqual(p_unsafe, 0.5, delta=0.02)

    def test_empty_or_unrelated_tokens_fail_closed(self):
        """Guarantees fail-closed behavior: returns 1.0 when neither token set is present."""
        top_logprobs = {
            "apple": -0.1,
            "banana": -0.2
        }
        p_unsafe, p_safe_sum, p_unsafe_sum = compute_unsafe_probability(top_logprobs)
        self.assertEqual(p_unsafe, 1.0)
        self.assertEqual(p_safe_sum, 0.0)
        self.assertEqual(p_unsafe_sum, 0.0)

    def test_empty_logprobs_dict_fails_closed(self):
        """Guarantees fail-closed behavior on empty top_logprobs dictionary."""
        p_unsafe, p_safe_sum, p_unsafe_sum = compute_unsafe_probability({})
        self.assertEqual(p_unsafe, 1.0)
        self.assertEqual(p_safe_sum, 0.0)
        self.assertEqual(p_unsafe_sum, 0.0)

    def test_custom_token_sets(self):
        """Tests passing custom safe and unsafe token sets."""
        custom_safe = {"allow", "permit"}
        custom_unsafe = {"deny", "block"}
        top_logprobs = {"allow": -0.1, "deny": -3.0}
        p_unsafe, p_safe_sum, p_unsafe_sum = compute_unsafe_probability(
            top_logprobs, safe_tokens=custom_safe, unsafe_tokens=custom_unsafe
        )
        self.assertLess(p_unsafe, 0.1)


if __name__ == "__main__":
    unittest.main()
