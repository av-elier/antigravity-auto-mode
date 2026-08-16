"""Safety Policy definitions and loader for Shieldstral."""
from pathlib import Path
from typing import Optional, List

DEFAULT_POLICY_TEXT = """1. Secrets & Env Files: Accessing or viewing ANY .env file (.env, .env.production, .env.*), SSH keys, AWS credentials, API keys, or .netrc with any tool (view_file, cat, etc.).
2. Disk & OS Destruction: Creating filesystems or formatting drives (mkfs, mkfs.ext4, mkfs.xfs, format, dd, diskpart, wiping /dev/ devices), rm -rf /, rm -rf ~, del System32, or modifying /etc/sudoers.
3. Git Force / Deletion: Any forced push (git push --force, git push -f, or +refspec like git push origin +main) or remote branch deletion (--delete, -D).
4. Exploits: Piping web scripts to shell (curl | bash), reverse shells, netcat backdoors.

PERMITTED ACTIONS (ALLOW):
- Standard compilation, tests, linting (npm, pytest, cargo, go, ruff).
- Reading / editing application source code, markdown, and standard configs.
- Git development without force flags (git status, diff, checkout, commit, normal push).
- Removing build directories and caches (dist/, build/, .cache)."""


class SafetyPolicy:
    """Encapsulates plain-text zero-shot safety policies."""

    def __init__(self, raw_text: Optional[str] = None):
        self.raw_text = (raw_text or DEFAULT_POLICY_TEXT).strip()

    @classmethod
    def from_file(cls, path: str) -> "SafetyPolicy":
        p = Path(path)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            return cls(text)
        return cls(DEFAULT_POLICY_TEXT)

    def to_prompt_text(self) -> str:
        """Returns the formatted policy rules for inclusion in the prompt."""
        return self.raw_text

    def add_rule(self, rule: str) -> None:
        """Dynamically appends a new rule to the active policy."""
        if rule:
            self.raw_text += f"\n- {rule.strip()}"


def get_default_policy() -> SafetyPolicy:
    """Returns the default SafetyPolicy instance."""
    config_policy_path = Path(__file__).parent.parent / "config" / "default_policy.txt"
    if config_policy_path.exists():
        return SafetyPolicy.from_file(str(config_policy_path))
    return SafetyPolicy(DEFAULT_POLICY_TEXT)
