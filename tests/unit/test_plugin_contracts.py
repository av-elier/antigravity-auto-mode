"""Unit tests for Antigravity plugin manifest, hooks, and sidecar JSON contracts.

Tag: @pytest.mark.unit, @pytest.mark.sidecar
Guarantees: Conformance with Google Antigravity Plugin and Hooks Specifications.
"""
import json
import unittest
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.unit
@pytest.mark.sidecar
class TestPluginContracts(unittest.TestCase):
    """Verifies schema validity and consistency across all Antigravity plugin descriptor files."""

    def test_plugin_json_schema_and_validity(self):
        """Validates plugin.json conforms to the Antigravity Plugin schema."""
        plugin_file = PROJECT_ROOT / "plugin.json"
        self.assertTrue(plugin_file.exists(), "plugin.json must exist in the root directory")

        with open(plugin_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("name"), "antigravity-auto-mode")
        self.assertIn("description", data)
        self.assertIn("version", data)

    def test_hooks_json_schema_and_script_references(self):
        """Validates hooks.json conforms to the Google Antigravity Hooks specification."""
        hooks_file = PROJECT_ROOT / "hooks.json"
        self.assertTrue(hooks_file.exists(), "hooks.json must exist in the root directory")

        with open(hooks_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("shieldstral-auto-guard", data)
        guard_hook_cfg = data["shieldstral-auto-guard"]
        self.assertTrue(guard_hook_cfg.get("enabled"))
        self.assertIn("PreToolUse", guard_hook_cfg)

        pre_tool_use = guard_hook_cfg["PreToolUse"]
        self.assertIsInstance(pre_tool_use, list)
        self.assertGreater(len(pre_tool_use), 0)

        entry = pre_tool_use[0]
        self.assertEqual(entry.get("matcher"), ".*")
        self.assertIn("hooks", entry)
        self.assertGreater(len(entry["hooks"]), 0)

        hook_def = entry["hooks"][0]
        self.assertEqual(hook_def.get("type"), "command")
        self.assertIn("scripts/eval_guard.py", hook_def.get("command", ""))
        self.assertGreater(hook_def.get("timeout", 0), 0)

        # Verify the referenced hook script actually exists on disk
        script_path = PROJECT_ROOT / "scripts" / "eval_guard.py"
        self.assertTrue(script_path.exists(), f"Referenced hook script {script_path} must exist")

    def test_sidecar_json_schema_and_script_references(self):
        """Validates sidecars/shieldstral-daemon/sidecar.json conforms to sidecar specification."""
        sidecar_file = PROJECT_ROOT / "sidecars" / "shieldstral-daemon" / "sidecar.json"
        self.assertTrue(sidecar_file.exists(), "sidecar.json must exist in sidecars/shieldstral-daemon/")

        with open(sidecar_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Must specify either 'command' or 'builtin' (mutually exclusive)
        has_command = "command" in data
        has_builtin = "builtin" in data
        self.assertTrue(has_command ^ has_builtin, "Exactly one of 'command' or 'builtin' must be specified.")

        self.assertEqual(data.get("command"), "python")
        self.assertIn("args", data)
        self.assertIn("run_daemon.py", data["args"])
        self.assertEqual(data.get("restart_policy"), "always")
        self.assertIn("display_name", data)
        self.assertIn("description", data)

        # Verify daemon entrypoint exists
        run_daemon_file = PROJECT_ROOT / "sidecars" / "shieldstral-daemon" / "run_daemon.py"
        self.assertTrue(run_daemon_file.exists(), "run_daemon.py must exist in sidecar directory")

    def test_config_json_defaults_and_keys(self):
        """Validates config/config.json has required daemon and guard configuration sections."""
        config_file = PROJECT_ROOT / "config" / "config.json"
        self.assertTrue(config_file.exists(), "config/config.json must exist")

        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("daemon", data)
        self.assertIn("guard", data)

        daemon_cfg = data["daemon"]
        self.assertIn("host", daemon_cfg)
        self.assertIn("port", daemon_cfg)
        self.assertIn("model_path", daemon_cfg)
        self.assertIn("timeout_seconds", daemon_cfg)

        guard_cfg = data["guard"]
        self.assertIn("unsafe_threshold", guard_cfg)
        self.assertIn("unsafe_decision", guard_cfg)
        self.assertIn("fail_closed_decision", guard_cfg)
        self.assertIn("cache_enabled", guard_cfg)
        self.assertIn("read_only_tools", guard_cfg)
        self.assertIsInstance(guard_cfg["read_only_tools"], list)


if __name__ == "__main__":
    unittest.main()
