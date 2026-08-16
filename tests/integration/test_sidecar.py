"""Unit and integration tests for Antigravity Sidecar configuration and lifecycle.

Tag: @pytest.mark.integration, @pytest.mark.sidecar
Guarantees: Sidecar specification compliance, dynamic port discovery, and installation.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
from scripts.install import install_plugin, enable_sidecar_in_config


def wait_for_endpoint_ready(url: str, timeout: float = 3.0) -> dict:
    """Fast polling helper for daemon startup to minimize test latency."""
    start = time.perf_counter()
    health_url = f"{url.rstrip('/')}/health"
    while time.perf_counter() - start < timeout:
        try:
            req = urllib.request.Request(health_url)
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            time.sleep(0.05)
    raise TimeoutError(f"Daemon at {url} did not become ready within {timeout}s")


@pytest.mark.integration
@pytest.mark.sidecar
class TestSidecarIntegration(unittest.TestCase):
    """Test suite for Antigravity Sidecar definition, execution, and registration."""

    def setUp(self):
        self.sidecar_dir = PROJECT_ROOT / "sidecars" / "shieldstral-daemon"
        self.sidecar_json = self.sidecar_dir / "sidecar.json"
        self.run_daemon_py = self.sidecar_dir / "run_daemon.py"

    def test_sidecar_json_validity_and_schema(self):
        """Validates sidecar.json against the Antigravity Sidecar specification."""
        self.assertTrue(self.sidecar_json.exists(), "sidecar.json must exist in sidecars/shieldstral-daemon/")

        with open(self.sidecar_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Must have command or builtin (mutually exclusive)
        has_command = "command" in data
        has_builtin = "builtin" in data
        self.assertTrue(has_command ^ has_builtin, "Exactly one of 'command' or 'builtin' must be specified.")

        self.assertEqual(data.get("command"), "python")
        self.assertIn("run_daemon.py", data.get("args", []))
        self.assertEqual(data.get("restart_policy"), "always")
        self.assertIn("display_name", data)
        self.assertIn("description", data)

    def test_enable_sidecar_in_config(self):
        """Tests writing sidecar activation to a config.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            sidecar_id = "antigravity-auto-mode/shieldstral-daemon"

            # Initial write
            res = enable_sidecar_in_config(config_dir, sidecar_id)
            self.assertTrue(res)

            config_path = config_dir / "config.json"
            self.assertTrue(config_path.exists())

            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertIn("sidecars", data)
            self.assertIn(sidecar_id, data["sidecars"])
            self.assertTrue(data["sidecars"][sidecar_id]["enabled"])

            # Idempotent re-write with existing keys
            data["other_setting"] = True
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            res2 = enable_sidecar_in_config(config_dir, sidecar_id)
            self.assertTrue(res2)

            with open(config_path, "r", encoding="utf-8") as f:
                data2 = json.load(f)
            self.assertTrue(data2["other_setting"])
            self.assertTrue(data2["sidecars"][sidecar_id]["enabled"])

    def test_install_plugin_copies_sidecars(self):
        """Tests that scripts/install.py copies sidecars/ to the installation destination."""
        with tempfile.TemporaryDirectory() as tmpdir:
            install_plugin(global_install=False, target_dir=tmpdir, enable_sidecar=True)

            dest = Path(tmpdir) / "plugins" / "antigravity-auto-mode"
            installed_sidecar_json = dest / "sidecars" / "shieldstral-daemon" / "sidecar.json"
            installed_run_daemon = dest / "sidecars" / "shieldstral-daemon" / "run_daemon.py"

            self.assertTrue(installed_sidecar_json.exists(), "sidecar.json must be copied by install.py")
            self.assertTrue(installed_run_daemon.exists(), "run_daemon.py must be copied by install.py")

            config_json = Path(tmpdir) / "config.json"
            self.assertTrue(config_json.exists())
            with open(config_json, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertTrue(cfg["sidecars"]["antigravity-auto-mode/shieldstral-daemon"]["enabled"])

    def test_run_daemon_mock_execution(self):
        """Tests executing run_daemon.py in mock mode on a dedicated port."""
        test_port = 8189
        cmd = [
            sys.executable,
            str(self.run_daemon_py),
            "--port", str(test_port),
            "--mock"
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.sidecar_dir)
        )

        try:
            # Fast polling for server startup
            data = wait_for_endpoint_ready(f"http://127.0.0.1:{test_port}")
            self.assertEqual(data.get("status"), "healthy")
            self.assertEqual(data.get("engine"), "mock")

            # Evaluate check
            eval_req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/evaluate",
                data=json.dumps({"tool": "run_command", "args": {"CommandLine": "npm test"}}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(eval_req, timeout=3.0) as resp:
                eval_data = json.loads(resp.read().decode("utf-8"))

            self.assertTrue(eval_data.get("is_safe"))
            self.assertLess(eval_data.get("p_unsafe"), 0.20)

            # Shutdown
            shutdown_req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/shutdown",
                data=b"{}",
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(shutdown_req, timeout=3.0)
            proc.wait(timeout=3.0)
        finally:
            if proc.poll() is None:
                proc.kill()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

    def test_run_daemon_dynamic_ephemeral_port_resolution(self):
        """Tests launching run_daemon.py with --port 0 and dynamic discovery via resolve_daemon_url."""
        from client.eval_client import resolve_daemon_url
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["ANTIGRAVITY_EXECUTABLE_DATA_DIR"] = tmpdir

            cmd = [
                sys.executable,
                str(self.run_daemon_py),
                "--port", "0",
                "--mock"
            ]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.sidecar_dir),
                env=env
            )

            try:
                # Fast poll for endpoint file creation
                start_wait = time.perf_counter()
                endpoint_file = Path(tmpdir) / "endpoint.json"
                while time.perf_counter() - start_wait < 3.0 and not endpoint_file.exists():
                    time.sleep(0.05)

                self.assertTrue(endpoint_file.exists(), "Dynamic endpoint file must be written to ANTIGRAVITY_EXECUTABLE_DATA_DIR")

                resolved_url = resolve_daemon_url()
                self.assertTrue(resolved_url.startswith("http://127.0.0.1:"))

                # Query dynamically resolved health endpoint
                data = wait_for_endpoint_ready(resolved_url)
                self.assertEqual(data.get("status"), "healthy")

                # Shutdown
                shutdown_req = urllib.request.Request(
                    f"{resolved_url}/shutdown",
                    data=b"{}",
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(shutdown_req, timeout=3.0)
                proc.wait(timeout=3.0)
            finally:
                if proc.poll() is None:
                    proc.kill()
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
