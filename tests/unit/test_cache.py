"""Unit tests for SHA-256 caching and persistence.

Tag: @pytest.mark.unit, @pytest.mark.cache
Guarantees: Deterministic SHA-256 hash across dict orderings, TTL invalidation, atomic persistence.
"""
import time
import unittest
import tempfile
import shutil
import pytest
from pathlib import Path

from client.cache import GuardCache, get_cache_key


@pytest.mark.unit
@pytest.mark.cache
class TestGuardCache(unittest.TestCase):
    """Verifies safe cache hashing, serialization, and TTL invalidation."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache_file = self.temp_dir / "test_cache.json"
        self.cache = GuardCache(cache_file=str(self.cache_file), ttl_seconds=0.1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_key_deterministic_ordering(self):
        """Validates that nested dict key order does not affect the generated SHA-256 hash."""
        args1 = {"b": 2, "a": 1, "nested": {"z": 10, "y": 20}}
        args2 = {"nested": {"y": 20, "z": 10}, "a": 1, "b": 2}

        k1 = get_cache_key("run_command", args1)
        k2 = get_cache_key("run_command", args2)

        self.assertEqual(k1, k2)
        self.assertEqual(len(k1), 64)  # Valid SHA-256 hex string

    def test_cache_hit_miss_and_persistence(self):
        """Tests miss -> mark_safe -> hit cycle and persistence to disk."""
        key = get_cache_key("run_command", {"CommandLine": "npm test"})

        # Initial state: Miss
        self.assertFalse(self.cache.is_safe(key))

        # Mark safe & verify Hit
        self.cache.mark_safe(key)
        self.assertTrue(self.cache.is_safe(key))
        self.assertTrue(self.cache_file.exists())

        # Reload from disk in a fresh instance
        reloaded_cache = GuardCache(cache_file=str(self.cache_file), ttl_seconds=0.1)
        self.assertTrue(reloaded_cache.is_safe(key))

    def test_cache_ttl_expiration(self):
        """Tests automatic entry invalidation upon TTL expiration."""
        key = get_cache_key("run_command", {"CommandLine": "cargo test"})
        self.cache.mark_safe(key)
        self.assertTrue(self.cache.is_safe(key))

        # Wait for TTL expiration (0.1s)
        time.sleep(0.15)
        self.assertFalse(self.cache.is_safe(key))

    def test_clear_cache(self):
        """Tests flushing all entries from memory and disk."""
        key1 = get_cache_key("tool1", {})
        key2 = get_cache_key("tool2", {})
        self.cache.mark_safe(key1)
        self.cache.mark_safe(key2)
        self.assertEqual(len(self.cache), 2)

        self.cache.clear()
        self.assertEqual(len(self.cache), 0)
        self.assertFalse(self.cache.is_safe(key1))


if __name__ == "__main__":
    unittest.main()
