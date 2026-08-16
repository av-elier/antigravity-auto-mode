#!/usr/bin/env python3
"""
Antigravity PreToolUse Hook Client: Shieldstral Guardrail
Zero-dependency client executed by Antigravity CLI / agent before tool execution.

Input: JSON on stdin (Antigravity PreToolUse format)
Output: JSON on stdout (decision: 'allow' | 'force_ask')
Exit Code: Always 0 (Antigravity 2.0 JSON contract requirement)
"""
import sys
import os
import json
import hashlib
import urllib.request
import urllib.error
import time
from pathlib import Path

# Add project root to sys.path if needed
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from client.eval_client import run_hook
except ImportError:
    def _resolve_fallback_url() -> str:
        if "AGY_GUARD_URL" in os.environ:
            return os.environ["AGY_GUARD_URL"]
        if "AGY_GUARD_PORT" in os.environ:
            host = os.environ.get("AGY_GUARD_HOST", "127.0.0.1")
            return f"http://{host}:{os.environ['AGY_GUARD_PORT']}/evaluate"

        discovery_files = []
        if "ANTIGRAVITY_EXECUTABLE_DATA_DIR" in os.environ:
            discovery_files.append(Path(os.environ["ANTIGRAVITY_EXECUTABLE_DATA_DIR"]) / "endpoint.json")
        discovery_files.extend([
            Path.home() / ".gemini" / "antigravity" / "sidecar_data" / "antigravity-auto-mode" / "shieldstral-daemon" / "endpoint.json",
            Path.home() / ".gemini" / "antigravity" / "sidecar_data" / "agy-shieldstral-guard" / "shieldstral-daemon" / "endpoint.json",
            PROJECT_ROOT / ".cache" / "endpoint.json",
            Path.home() / ".cache" / "antigravity_auto_mode_endpoint.json",
            Path.home() / ".cache" / "agy_shieldstral_guard_endpoint.json"
        ])
        for ep in discovery_files:
            if ep.exists():
                try:
                    with open(ep, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        url = data.get("url")
                        if url:
                            return f"{url.rstrip('/')}/evaluate"
                except Exception:
                    pass
        return "http://127.0.0.1:8080/evaluate"

    DEFAULT_CONFIG = {
        "daemon_url": _resolve_fallback_url(),
        "threshold": float(os.environ.get("AGY_GUARD_THRESHOLD", 0.20)),
        "timeout": float(os.environ.get("AGY_GUARD_TIMEOUT", 5.0)),
        "cache_file": Path.home() / ".cache" / "agy_guard_safe_cache.json"
    }

    def get_cache_key(tool: str, args: any) -> str:
        try:
            args_str = json.dumps(args, sort_keys=True, separators=(",", ":"))
        except Exception:
            args_str = str(args)
        return hashlib.sha256(f"{tool}:{args_str}".encode("utf-8")).hexdigest()

    def run_hook(stdin_data=None) -> int:
        if stdin_data is None:
            try:
                stdin_data = sys.stdin.read()
            except Exception:
                stdin_data = ""

        if not stdin_data.strip():
            sys.stdout.write(json.dumps({"decision": "allow", "reason": "Empty input"}) + "\n")
            return 0

        try:
            payload = json.loads(stdin_data)
        except Exception:
            sys.stdout.write(json.dumps({"decision": "force_ask", "reason": "Invalid JSON input payload"}) + "\n")
            return 0

        if "toolCall" in payload:
            tool = payload["toolCall"].get("name", "")
            args = payload["toolCall"].get("args", {})
        else:
            tool = payload.get("tool", "")
            args = payload.get("args", {})

        cache_key = get_cache_key(tool, args)
        cache_file = DEFAULT_CONFIG["cache_file"]

        # Fast path: Cache
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache = set(json.load(f))
                if cache_key in cache:
                    sys.stdout.write(json.dumps({"decision": "allow", "reason": "Cached safe action"}) + "\n")
                    return 0
            except Exception:
                cache = set()
        else:
            cache = set()

        # Query Daemon
        req_payload = json.dumps({"tool": tool, "args": args}).encode("utf-8")
        req = urllib.request.Request(
            DEFAULT_CONFIG["daemon_url"],
            data=req_payload,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=DEFAULT_CONFIG["timeout"]) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
            p_unsafe = float(res_data.get("p_unsafe", 1.0))

            if p_unsafe < DEFAULT_CONFIG["threshold"]:
                cache.add(cache_key)
                try:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(list(cache), f)
                except Exception:
                    pass
                sys.stdout.write(json.dumps({
                    "decision": "allow",
                    "reason": f"Shieldstral approved (P(Unsafe)={p_unsafe:.2f} < {DEFAULT_CONFIG['threshold']:.2f})"
                }) + "\n")
                return 0
            else:
                sys.stdout.write(json.dumps({
                    "decision": "force_ask",
                    "reason": f"Shieldstral flagged unsafe (P(Unsafe)={p_unsafe:.2f} >= {DEFAULT_CONFIG['threshold']:.2f})"
                }) + "\n")
                print(f"[Security Gate] Action '{tool}' flagged unsafe (P={p_unsafe:.2f})", file=sys.stderr)
                return 0

        except Exception as e:
            # Deterministic fail-closed fallback
            sys.stdout.write(json.dumps({
                "decision": "force_ask",
                "reason": f"Daemon unreachable: {type(e).__name__} (Fail-Closed)"
            }) + "\n")
            return 0


if __name__ == "__main__":
    sys.exit(run_hook())
