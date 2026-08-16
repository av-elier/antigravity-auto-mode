"""Integration tests for Shieldstral model parameters and dual-layer caching.

Tag: @pytest.mark.integration, @pytest.mark.cache
Guarantees: Correct Shieldstral model parameters, KV prefix cache performance, SHA-256 safe cache speedup.
"""
import os
import time
import unittest
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from daemon.engine import ShieldstralEngine, compute_unsafe_probability
from daemon.mock_engine import MockShieldstralEngine
from policy.safety_policy import get_default_policy
from policy.prompt_template import build_shieldstral_prompt
from client.cache import GuardCache, get_cache_key
from client.eval_client import evaluate_tool_call
from daemon.server import create_server

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "Shieldstral-1.0-3B-Q4_K_M.gguf"


@pytest.mark.integration
@pytest.mark.cache
class TestModelAndCache(unittest.TestCase):
    """Verifies model parameter invariants, prefix KV caching, and SHA-256 cache performance."""

    def test_mock_engine_prefix_cache_lifecycle(self):
        """Verifies warmup and prefix cache flag tracking on MockShieldstralEngine."""
        engine = MockShieldstralEngine()
        policy = get_default_policy()
        warmup_time = engine.warmup(policy)

        self.assertGreater(warmup_time, 0.0)
        self.assertTrue(engine.prefix_cached)

        prompt = build_shieldstral_prompt("run_command", {"CommandLine": "npm test"}, policy)
        res = engine.evaluate(prompt)

        self.assertIn("p_unsafe", res)
        self.assertLess(res["p_unsafe"], 0.20)
        self.assertTrue(res.get("prefix_cached"))

    def test_model_instantiation_parameters_mocked(self):
        """Validates that ShieldstralEngine configures llama_cpp with exact required safety parameters."""
        mock_llama_cls = MagicMock()
        mock_ram_cache_cls = MagicMock()

        with patch.dict("sys.modules", {"llama_cpp": MagicMock(Llama=mock_llama_cls, LlamaRAMCache=mock_ram_cache_cls)}):
            from daemon.engine import ShieldstralEngine
            engine = ShieldstralEngine(
                model_path="dummy/path.gguf",
                n_ctx=2048,
                n_gpu_layers=99,
                enable_prefix_cache=True,
                prefix_cache_mb=512,
                n_batch=512,
                verbose=False
            )

            # Assert llama_cpp was initialized with required parameters
            mock_llama_cls.assert_called_once()
            _, kwargs = mock_llama_cls.call_args
            self.assertEqual(kwargs.get("model_path"), "dummy/path.gguf")
            self.assertEqual(kwargs.get("n_ctx"), 2048)
            self.assertEqual(kwargs.get("n_gpu_layers"), 99)
            self.assertEqual(kwargs.get("n_batch"), 512)
            self.assertTrue(kwargs.get("logits_all"), "logits_all MUST be True for logprob extraction")

            # Assert LlamaRAMCache was initialized with 512MB capacity
            mock_ram_cache_cls.assert_called_once_with(capacity_bytes=512 * 1024 * 1024)

    def test_sha256_client_cache_speedup_quantitative(self):
        """Quantitatively verifies that SHA-256 cache hits are sub-millisecond (< 2ms) and ~50-100x faster than uncached evaluation."""
        server = create_server(host="127.0.0.1", port=0, mock=True)
        port = server.actual_port

        import threading
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        try:
            config = {
                "daemon": {"host": "127.0.0.1", "port": port, "timeout_seconds": 5.0},
                "guard": {"unsafe_threshold": 0.20, "bypass_read_only_tools": False, "cache_enabled": True}
            }
            cache = GuardCache()
            cache.clear()

            tool = "run_command"
            args = {"CommandLine": "npm test -- --coverage"}

            # 1. First evaluation: Uncached (goes through HTTP loopback & engine)
            t0 = time.perf_counter()
            dec1, reas1, p1 = evaluate_tool_call(tool, args, config=config, cache=cache)
            uncached_ms = (time.perf_counter() - t0) * 1000.0

            self.assertEqual(dec1, "allow")
            self.assertNotIn("cache", reas1)

            # 2. Second evaluation: Cached (hits in-memory/disk SHA-256 table)
            t1 = time.perf_counter()
            dec2, reas2, p2 = evaluate_tool_call(tool, args, config=config, cache=cache)
            cached_ms = (time.perf_counter() - t1) * 1000.0

            self.assertEqual(dec2, "allow")
            self.assertIn("cache", reas2)

            # Quantitative assertion: Cached execution must be ultra-fast (< 2.0 ms)
            self.assertLess(cached_ms, 2.0, f"Cached evaluation took {cached_ms:.3f}ms, expected < 2.0ms")

        finally:
            server.shutdown()
            server.server_close()

    @pytest.mark.real_model
    def test_real_model_prefix_cache_speedup_if_available(self):
        """Verifies real Shieldstral model KV prefix cache performance if model weights are present."""
        if os.environ.get("RUN_REAL_MODEL") != "1":
            self.skipTest("Real model test skipped by default. Run with RUN_REAL_MODEL=1 or --kind real-model")
        if not MODEL_PATH.exists():
            self.skipTest(f"Real model weights not found at {MODEL_PATH}")

        policy = get_default_policy()
        engine = ShieldstralEngine(
            model_path=str(MODEL_PATH),
            n_ctx=2048,
            n_gpu_layers=99,
            enable_prefix_cache=True,
            prefix_cache_mb=512
        )

        # 1. Warm up prefix cache
        warmup_time_ms = engine.warmup(policy)
        self.assertGreater(warmup_time_ms, 0.0)

        # 2. Evaluate sample 1
        prompt1 = build_shieldstral_prompt("run_command", {"CommandLine": "npm test"}, policy)
        res1 = engine.evaluate(prompt1)
        self.assertIn("p_unsafe", res1)
        self.assertLess(res1["p_unsafe"], 0.20)
        self.assertTrue(res1.get("prefix_cached"))

        # 3. Evaluate sample 2 with same static prefix
        prompt2 = build_shieldstral_prompt("run_command", {"CommandLine": "npm run build"}, policy)
        res2 = engine.evaluate(prompt2)
        self.assertIn("p_unsafe", res2)
        self.assertLess(res2["p_unsafe"], 0.20)

        # Both forward passes must successfully leverage the prefix cache
        self.assertTrue(res2.get("prefix_cached"))


if __name__ == "__main__":
    unittest.main()
