"""Integration tests for HTTP Daemon endpoints.

Tag: @pytest.mark.integration
Guarantees: Full endpoint contracts, concurrency resilience, dynamic port 0 allocation.
"""
import concurrent.futures
import json
import threading
import time
import unittest
import urllib.request
import urllib.error
import pytest

from daemon.server import create_server


@pytest.mark.integration
class TestDaemonServer(unittest.TestCase):
    """Verifies all HTTP endpoints, concurrent load handling, and dynamic port binding."""
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

    def test_health_endpoint(self):
        """Verifies GET /health returns status, engine type, and prefix cache flag."""
        url = f"http://127.0.0.1:{self.port}/health"
        with urllib.request.urlopen(url, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(resp.status, 200)
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["engine"], "mock")
            self.assertIn("prefix_cache", data)

    def test_evaluate_benign_command(self):
        """Verifies POST /evaluate auto-approves safe commands with low P(Unsafe)."""
        url = f"http://127.0.0.1:{self.port}/evaluate"
        payload = json.dumps({
            "tool": "run_command",
            "args": {"CommandLine": "npm test"}
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(resp.status, 200)
            self.assertLess(data["p_unsafe"], 0.20)
            self.assertTrue(data["is_safe"])
            self.assertIn("top_logprobs", data)

    def test_evaluate_dangerous_command(self):
        """Verifies POST /evaluate blocks dangerous commands with high P(Unsafe)."""
        url = f"http://127.0.0.1:{self.port}/evaluate"
        payload = json.dumps({
            "tool": "run_command",
            "args": {"CommandLine": "rm -rf /"}
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(resp.status, 200)
            self.assertGreaterEqual(data["p_unsafe"], 0.20)
            self.assertFalse(data["is_safe"])

    def test_evaluate_massive_payload_no_timeout(self):
        """Verifies POST /evaluate sanitizes and processes 50KB payloads without timing out."""
        url = f"http://127.0.0.1:{self.port}/evaluate"
        payload = json.dumps({
            "tool": "write_to_file",
            "args": {
                "TargetFile": "/workspace/large.txt",
                "CodeContent": "A" * 50000,
                "Description": "Large file write"
            }
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = (time.perf_counter() - start) * 1000.0
            self.assertEqual(resp.status, 200)
            self.assertTrue(data["is_safe"])
            self.assertLess(elapsed, 2000.0)

    def test_concurrent_requests_handling(self):
        """Verifies daemon processes multiple concurrent requests safely across threads."""
        url = f"http://127.0.0.1:{self.port}/evaluate"

        def _send_req(cmd):
            payload = json.dumps({"tool": "run_command", "args": {"CommandLine": cmd}}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode("utf-8"))

        commands = ["npm test", "pytest", "git status", "cargo build", "echo hi"] * 3
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(_send_req, commands))

        self.assertEqual(len(results), 15)
        for r in results:
            self.assertTrue(r["is_safe"])

    def test_basic_load_and_average_latency(self):
        """Verifies daemon average loopback latency is well within budget (< 50ms)."""
        url = f"http://127.0.0.1:{self.port}/evaluate"
        num_requests = 20
        latencies = []

        for i in range(num_requests):
            payload = json.dumps({"tool": "run_command", "args": {"CommandLine": f"git log -n {i}"}}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latencies.append((time.perf_counter() - t0) * 1000.0)
                self.assertEqual(resp.status, 200)

        avg_latency = sum(latencies) / len(latencies)
        self.assertLess(avg_latency, 50.0, f"Average roundtrip latency {avg_latency:.2f}ms exceeded 50ms limit")

    def test_policy_and_metrics_endpoints(self):
        """Verifies GET /policy and GET /metrics return correct metadata and counts."""
        url_pol = f"http://127.0.0.1:{self.port}/policy"
        with urllib.request.urlopen(url_pol, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("policy", data)

        url_met = f"http://127.0.0.1:{self.port}/metrics"
        with urllib.request.urlopen(url_met, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertGreaterEqual(data["requests_total"], 2)
            self.assertGreaterEqual(data["safe_count"], 1)

    def test_dynamic_port_zero_binding(self):
        """Tests that passing port 0 allocates an ephemeral port and writes endpoint file."""
        server = create_server(host="127.0.0.1", port=0, mock=True)
        try:
            actual_port = server.actual_port
            self.assertGreater(actual_port, 0)
            self.assertNotEqual(actual_port, 8080)
            self.assertTrue(hasattr(server, "endpoint_files"))
            self.assertGreater(len(server.endpoint_files), 0)
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()
