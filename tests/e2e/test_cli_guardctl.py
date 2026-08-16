"""End-to-End tests for guardctl CLI management utility.

Tag: @pytest.mark.e2e
Guarantees: Correct execution and outputs for all CLI subcommands.
"""
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import pytest
from pathlib import Path

from daemon.server import create_server

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.e2e
class TestCliGuardctl(unittest.TestCase):
    """End-to-end verification of the guardctl command-line interface."""
    server = None
    server_thread = None
    port = 0

    @classmethod
    def setUpClass(cls):
        # Use dynamic ephemeral port (port=0) to prevent port collisions
        cls.server = create_server(host="127.0.0.1", port=0, mock=True)
        cls.port = cls.server.actual_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()

    def _run_guardctl(self, args: list) -> subprocess.CompletedProcess:
        """Helper to run python -m cli.guardctl with environment pointing to test server."""
        env = dict(sys.modules["os"].environ)
        env["AGY_GUARD_PORT"] = str(self.port)
        return subprocess.run(
            [sys.executable, "-m", "cli.guardctl"] + args,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            env=env
        )

    def test_guardctl_status(self):
        """Verifies 'guardctl status' displays health, metrics, and endpoint info."""
        res = self._run_guardctl(["status", "--port", str(self.port)])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Shieldstral Guardrail Daemon Status", res.stdout)
        self.assertIn("HEALTHY", res.stdout)
        self.assertIn("Metrics", res.stdout)

    def test_guardctl_policy(self):
        """Verifies 'guardctl policy' prints active safety rules."""
        res = self._run_guardctl(["policy"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Active Shieldstral Safety Policy", res.stdout)
        self.assertIn("CRITICAL VIOLATIONS", res.stdout)

    def test_guardctl_clear_cache(self):
        """Verifies 'guardctl clear-cache' flushes entries."""
        res = self._run_guardctl(["clear-cache"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Safe cache cleared", res.stdout)

    def test_guardctl_test_benign_and_dangerous(self):
        """Verifies 'guardctl test' accurately evaluates benign and dangerous actions."""
        # 1. Benign tool call
        res_safe = self._run_guardctl(["test", "--tool", "run_command", "--args", '{"CommandLine": "pytest"}'])
        self.assertEqual(res_safe.returncode, 0)
        self.assertIn("ALLOW", res_safe.stdout)

        # 2. Destructive tool call
        res_unsafe = self._run_guardctl(["test", "--tool", "run_command", "--args", '{"CommandLine": "rm -rf /"}'])
        self.assertEqual(res_unsafe.returncode, 0)
        self.assertIn("ASK", res_unsafe.stdout)

    def test_guardctl_benchmark(self):
        """Verifies 'guardctl benchmark -n 5' executes benchmark loop."""
        res = self._run_guardctl(["benchmark", "-n", "5"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Benchmark Results", res.stdout)
        self.assertIn("Average Latency", res.stdout)

    def test_guardctl_logs(self):
        """Verifies 'guardctl logs -n 5' executes cleanly."""
        res = self._run_guardctl(["logs", "-n", "5"])
        self.assertEqual(res.returncode, 0)

    def test_guardctl_eval_mock(self):
        """Verifies 'guardctl eval --mock' executes benchmark dataset on mock engine."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "eval_out.json"
            res = self._run_guardctl(["eval", "--mock", "--output", str(out_file)])
            self.assertEqual(res.returncode, 0)
            self.assertIn("Shieldstral Guardrail Evaluation Benchmark Report", res.stdout)
            self.assertTrue(out_file.exists())
            with open(out_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertGreater(data.get("accuracy", 0), 90)


if __name__ == "__main__":
    unittest.main()
