"""Unit and integration tests for Antigravity PreToolUse hook client.

Tag: @pytest.mark.integration
Guarantees: Antigravity JSON contract parsing, fail-closed handling, cache acceleration.
"""
import json
import os
import tempfile
import unittest
import threading
import time
import pytest
from pathlib import Path
from io import StringIO
from unittest.mock import patch

from client.eval_client import evaluate_tool_call, run_hook, load_config
from client.cache import GuardCache
from daemon.server import create_server


@pytest.mark.integration
class TestHookClient(unittest.TestCase):
    """Verifies PreToolUse hook evaluations, fail-closed mechanics, and client configuration."""
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

    def setUp(self):
        self.config = {
            "daemon": {"host": "127.0.0.1", "port": self.port, "timeout_seconds": 5.0},
            "guard": {
                "unsafe_threshold": 0.20,
                "bypass_read_only_tools": False,
                "cache_enabled": True
            }
        }
        self.temp_dir = tempfile.mkdtemp()
        self.cache = GuardCache(cache_file=str(Path(self.temp_dir) / "cache.json"))

    def test_safe_file_view_evaluated_and_cached(self):
        """Verifies viewing safe source files is auto-approved."""
        decision, reason, p_unsafe = evaluate_tool_call(
            tool="view_file",
            args={"AbsolutePath": "src/components/Header.tsx"},
            config=self.config,
            cache=self.cache
        )
        self.assertEqual(decision, "allow")
        self.assertLess(p_unsafe, 0.20)

    def test_secret_file_view_triggers_ask(self):
        """Verifies viewing sensitive SSH keys triggers manual confirmation (force_ask)."""
        decision, reason, p_unsafe = evaluate_tool_call(
            tool="view_file",
            args={"AbsolutePath": "~/.ssh/id_rsa"},
            config=self.config,
            cache=self.cache
        )
        self.assertEqual(decision, "force_ask")
        self.assertGreaterEqual(p_unsafe, 0.20)
        self.assertIn("violation detected", reason)

    def test_read_only_tool_bypass_when_explicitly_enabled(self):
        """Verifies fast path bypass for configured read-only tools when bypass is active."""
        bypass_config = {
            "daemon": {"host": "127.0.0.1", "port": self.port, "timeout_seconds": 1.0},
            "guard": {
                "unsafe_threshold": 0.20,
                "bypass_read_only_tools": True,
                "read_only_tools": ["list_dir", "search_web"]
            }
        }
        decision, reason, p_unsafe = evaluate_tool_call(
            tool="list_dir",
            args={"DirectoryPath": "/tmp"},
            config=bypass_config,
            cache=self.cache
        )
        self.assertEqual(decision, "allow")
        self.assertEqual(p_unsafe, 0.0)
        self.assertIn("read tool", reason)

    def test_safe_command_evaluation_and_caching(self):
        """Verifies safe commands are evaluated and subsequent calls hit the SHA-256 cache."""
        tool = "run_command"
        args = {"CommandLine": "git status"}

        # 1. Uncached run -> Evaluated by daemon -> Allowed
        dec1, reas1, p1 = evaluate_tool_call(tool, args, config=self.config, cache=self.cache)
        self.assertEqual(dec1, "allow")
        self.assertLess(p1, 0.20)

        # 2. Cached run -> Hit cache -> Allowed instantly
        dec2, reas2, p2 = evaluate_tool_call(tool, args, config=self.config, cache=self.cache)
        self.assertEqual(dec2, "allow")
        self.assertIn("cache", reas2)

    def test_unsafe_command_triggers_ask(self):
        """Verifies destructive shell execution commands trigger force_ask."""
        tool = "run_command"
        args = {"CommandLine": "rm -rf /"}

        decision, reason, p_unsafe = evaluate_tool_call(tool, args, config=self.config, cache=self.cache)
        self.assertEqual(decision, "force_ask")
        self.assertGreaterEqual(p_unsafe, 0.20)
        self.assertIn("violation detected", reason)

    def test_fail_closed_when_daemon_offline(self):
        """Guarantees fail-closed safety: if daemon is unreachable, returns force_ask."""
        bad_config = {
            "daemon": {"host": "127.0.0.1", "port": 59999, "timeout_seconds": 0.5},
            "guard": {"unsafe_threshold": 0.20, "bypass_read_only_tools": False}
        }
        decision, reason, p_unsafe = evaluate_tool_call(
            "run_command",
            {"CommandLine": "npm test"},
            config=bad_config,
            cache=self.cache
        )
        self.assertEqual(decision, "force_ask")
        self.assertEqual(p_unsafe, 1.0)
        self.assertIn("Fail-Closed", reason)

    def test_run_hook_stdin_antigravity_schema(self):
        """Verifies run_hook parses standard Antigravity PreToolUse payload format."""
        payload = {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "pytest"}
            },
            "conversationId": "conv-123",
            "stepIdx": 5
        }

        with patch("client.eval_client.load_config", return_value=self.config):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = run_hook(json.dumps(payload))
                self.assertEqual(exit_code, 0)
                output = json.loads(mock_stdout.getvalue())
                self.assertEqual(output["decision"], "allow")

    def test_run_hook_malformed_json_fails_closed(self):
        """Guarantees fail-closed handling on non-JSON stdin."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = run_hook("not-json-at-all")
            self.assertEqual(exit_code, 0)
            output = json.loads(mock_stdout.getvalue())
            self.assertEqual(output["decision"], "force_ask")

    def test_load_config_env_timeout(self):
        """Tests AGY_GUARD_TIMEOUT environment variable override."""
        with patch.dict(os.environ, {"AGY_GUARD_TIMEOUT": "7.5"}):
            cfg = load_config()
            self.assertEqual(cfg["daemon"]["timeout_seconds"], 7.5)


if __name__ == "__main__":
    unittest.main()
