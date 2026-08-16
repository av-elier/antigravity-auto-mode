"""Unit tests for safety policies and prompt template construction.

Tag: @pytest.mark.unit
Guarantees: Deterministic prompt construction, template delimiters, payload sanitization.
"""
import unittest
import pytest
from policy.safety_policy import SafetyPolicy, get_default_policy
from policy.prompt_template import (
    build_shieldstral_prompt,
    format_tool_args,
    get_static_prefix,
    format_document_suffix,
    sanitize_and_truncate_tool_args,
)


@pytest.mark.unit
class TestPolicyAndPrompts(unittest.TestCase):
    """Verifies policy rule parsing, prompt formatting, and payload truncation."""

    def test_default_policy_content(self):
        """Verifies default policy includes critical categories and permitted actions."""
        policy = get_default_policy()
        text = policy.to_prompt_text()
        self.assertIn("Secrets & Env Files", text)
        self.assertIn("Disk & OS Destruction", text)
        self.assertIn("Exploits", text)
        self.assertIn("PERMITTED ACTIONS", text)

    def test_custom_policy_extension(self):
        """Verifies dynamic addition of custom rules."""
        policy = SafetyPolicy("Base rule: deny root operations.")
        policy.add_rule("Deny modifying docker containers.")
        text = policy.to_prompt_text()
        self.assertIn("Base rule: deny root operations.", text)
        self.assertIn("Deny modifying docker containers.", text)

    def test_prompt_formatting_delimiters(self):
        """Verifies Shieldstral instruction template delimiters and expected format."""
        tool = "run_command"
        args = {"CommandLine": "rm -rf /"}
        prompt = build_shieldstral_prompt(tool, args)

        self.assertTrue(prompt.startswith("[INST]"))
        self.assertTrue(prompt.endswith("[/INST]"))
        self.assertIn("<Instruct>:", prompt)
        self.assertIn("<Query>:", prompt)
        self.assertIn("<Document>:", prompt)
        self.assertIn("Tool: run_command", prompt)
        self.assertIn("rm -rf /", prompt)
        self.assertIn('Respond with exactly one token: "Yes" (violates policy) or "No"', prompt)

    def test_format_tool_args_string_and_dict(self):
        """Verifies formatting of string and dictionary tool arguments."""
        str_args = "pytest -v"
        self.assertEqual(format_tool_args(str_args), "pytest -v")

        dict_args = {"flag": True, "count": 5}
        formatted = format_tool_args(dict_args)
        self.assertIn('"count": 5', formatted)
        self.assertIn('"flag": true', formatted)

    def test_get_static_prefix_deterministic(self):
        """Verifies static prefix is deterministic to ensure 100% KV prefix cache hit rate."""
        policy = get_default_policy()
        prefix1 = get_static_prefix(policy)
        prefix2 = get_static_prefix(policy)
        self.assertEqual(prefix1, prefix2)
        self.assertTrue(prefix1.startswith("[INST] <Instruct>:"))
        self.assertTrue(prefix1.endswith("\n\n"))
        self.assertIn("Safety Policy Guidelines:", prefix1)

    def test_format_document_suffix(self):
        """Verifies dynamic suffix generation with Document and Query markers."""
        suffix = format_document_suffix("run_command", {"CommandLine": "npm test"})
        self.assertTrue(suffix.startswith("<Document>:"))
        self.assertTrue(suffix.endswith("[/INST]"))
        self.assertIn("Tool: run_command", suffix)
        self.assertIn("npm test", suffix)

    def test_sanitize_and_truncate_large_payloads(self):
        """Guarantees large tool argument payloads are truncated to prevent context overflow."""
        # 1. Massive write_to_file payload (50KB)
        huge_code = "print('hello world')\n" * 2500
        args = {
            "TargetFile": "/src/main.py",
            "Overwrite": True,
            "Description": "Create entry point",
            "CodeContent": huge_code
        }
        sanitized = sanitize_and_truncate_tool_args("write_to_file", args)
        self.assertEqual(sanitized["TargetFile"], "/src/main.py")
        self.assertEqual(sanitized["Description"], "Create entry point")
        self.assertIn("omitted", sanitized["CodeContent"])
        self.assertLess(len(sanitized["CodeContent"]), 1000)

        # 2. Massive replace_file_content payload
        replace_args = {
            "TargetFile": "/src/utils.py",
            "TargetContent": "def old():\n" + ("  pass\n" * 500),
            "ReplacementContent": "def new():\n" + ("  return True\n" * 500),
            "StartLine": 1,
            "EndLine": 500
        }
        sanitized_rep = sanitize_and_truncate_tool_args("replace_file_content", replace_args)
        self.assertEqual(sanitized_rep["TargetFile"], "/src/utils.py")
        self.assertIn("omitted", sanitized_rep["TargetContent"])
        self.assertIn("omitted", sanitized_rep["ReplacementContent"])

        # 3. Massive command line string
        cmd_args = {
            "CommandLine": "python -c '" + ("a = 1; " * 500) + "'"
        }
        sanitized_cmd = sanitize_and_truncate_tool_args("run_command", cmd_args)
        self.assertIn("omitted", sanitized_cmd["CommandLine"])
        self.assertLess(len(sanitized_cmd["CommandLine"]), 1500)


if __name__ == "__main__":
    unittest.main()
