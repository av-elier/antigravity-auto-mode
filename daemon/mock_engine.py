"""Mock inference engine for fast testing, validation, and offline development."""
import re
import time
import math
from typing import Dict, Any, List

DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+[/~]",
    r"del\s+/[fF]\s+/[sS]\s+/[qQ]",
    r"format\s+[a-zA-Z]:",
    r"diskpart",
    r"mkfs",
    r"/dev/zero\s+of=/dev/",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\};:", # Forkbomb
    r"curl\s+.*\|\s*(?:bash|sh|powershell|pwsh|python)",
    r"wget\s+.*\|\s*(?:bash|sh|powershell|pwsh|python)",
    r"(?:id_rsa|id_ed25519|\.netrc|\.aws/credentials|\.env|export\s+TOKEN|OPENAI_API_KEY|GEMINI_API_KEY)",
    r"/etc/sudoers",
    r"(?:drivers.*etc.*hosts|/etc/hosts)",
    r"git\s+push\s+.*(?:--force|-f\b|\+|--delete)",
    r"git\s+branch\s+-D\s+(?:main|master)",
    r"chmod\s+-R\s+777\s+/",
    r"chown\s+-R\s+.*(?:\s+/|\s+/etc|\s+/root|\s+/bin)",
    r"nc\s+.*-e\s+/bin/(?:sh|bash)",
    r"bash\s+-i\s+>& /dev/tcp",
    r"socket\.socket.*connect",
    r"/dev/null\s*;\s*rm",
    r"powershell\s+-enc",
    r"DROP\s+DATABASE",
    r"TRUNCATE\s+TABLE"
]

BENIGN_PATTERNS = [
    r"npm\s+(?:test|run|install|build|ci)",
    r"pytest",
    r"python\s+-m\s+unittest",
    r"git\s+(?:status|diff|log|add|commit|branch|checkout)",
    r"cargo\s+(?:build|test|check)",
    r"go\s+(?:test|build|vet)",
    r"echo\b",
    r"ls\b",
    r"dir\b",
    r"cat\b",
    r"pwd\b",
    r"mkdir\b"
]


class MockShieldstralEngine:
    """Deterministic mock inference engine generating synthetic logprobs."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.prefix_cached = False
        self.compiled_dangerous = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]
        self.compiled_benign = [re.compile(p, re.IGNORECASE) for p in BENIGN_PATTERNS]

    def warmup(self, policy: Any = None) -> float:
        """Simulates warmup for mock engine and marks prefix cache active."""
        self.prefix_cached = True
        return 1.0

    def evaluate(self, prompt: str) -> Dict[str, Any]:
        """Evaluates a prompt and generates synthetic logprobs."""
        start_time = time.perf_counter()

        # Extract only the target document / action section so examples in Safety Policy aren't matched
        action_match = re.search(r"(?:<Document>:|Planned Action:)\s*(.*)", prompt, re.DOTALL)
        target_text = action_match.group(1) if action_match else prompt

        # Check for dangerous signals in the planned action
        is_dangerous = any(pat.search(target_text) for pat in self.compiled_dangerous)
        is_benign = any(pat.search(target_text) for pat in self.compiled_benign)

        if is_dangerous:
            # High probability of unsafe (e.g. 0.95)
            # Logprob for Yes ~ ln(0.95) = -0.051, No ~ ln(0.05) = -2.995
            top_logprobs = {
                "Yes": -0.051,
                " Yes": -0.150,
                "No": -2.995,
                " No": -3.500,
                "maybe": -5.000
            }
            p_unsafe = 0.95
        elif is_benign:
            # Low probability of unsafe (e.g. 0.01)
            # Logprob for No ~ ln(0.99) = -0.010, Yes ~ ln(0.01) = -4.605
            top_logprobs = {
                "No": -0.010,
                " No": -0.050,
                "Yes": -4.605,
                " Yes": -5.200,
                "false": -6.000
            }
            p_unsafe = 0.01
        else:
            # Neutral / default safe for ordinary developer commands
            top_logprobs = {
                "No": -0.050,
                " No": -0.100,
                "Yes": -3.000,
                " Yes": -3.500
            }
            p_unsafe = 0.05

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        p_safe_sum = sum(math.exp(lp) for t, lp in top_logprobs.items() if t.strip().lower() in {"no", "false"})
        p_unsafe_sum = sum(math.exp(lp) for t, lp in top_logprobs.items() if t.strip().lower() in {"yes", "true"})
        total = p_safe_sum + p_unsafe_sum
        normalized_p_unsafe = (p_unsafe_sum / total) if total > 0 else p_unsafe

        return {
            "p_unsafe": normalized_p_unsafe,
            "p_safe_sum": p_safe_sum,
            "p_unsafe_sum": p_unsafe_sum,
            "top_logprobs": top_logprobs,
            "latency_ms": latency_ms,
            "prefix_cached": self.prefix_cached,
            "mock": True
        }
