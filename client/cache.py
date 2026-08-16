"""Local SHA-256 Read-Through Cache for safe tool executions."""
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Set


def get_cache_key(tool: str, args: Any) -> str:
    """
    Generates a deterministic SHA-256 digest for a given tool invocation.
    """
    try:
        args_str = json.dumps(args, sort_keys=True, separators=(",", ":"))
    except Exception:
        args_str = str(args)
    target = f"{tool}:{args_str}"
    return hashlib.sha256(target.encode("utf-8")).hexdigest()


class GuardCache:
    """Atomic, persistent read-through cache for safe evaluations."""

    def __init__(self, cache_file: Optional[str] = None, ttl_seconds: int = 86400):
        if cache_file:
            self.cache_path = Path(cache_file)
        else:
            # Default to local cache in user directory or repo cache
            self.cache_path = Path.cwd() / ".cache" / "agy_guard_safe_cache.json"
        
        self.ttl_seconds = ttl_seconds
        self._entries: Dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        """Loads entries from disk."""
        if not self.cache_path.exists():
            self._entries = {}
            return

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                now = time.time()
                # Support both simple list format and timestamped dict format
                if isinstance(data, list):
                    self._entries = {k: now for k in data}
                elif isinstance(data, dict):
                    # Filter out expired items
                    self._entries = {
                        k: ts for k, ts in data.items()
                        if (now - ts) < self.ttl_seconds
                    }
        except Exception:
            self._entries = {}

    def is_safe(self, cache_key: str) -> bool:
        """Checks if a cache key exists and is within TTL."""
        if cache_key in self._entries:
            ts = self._entries[cache_key]
            if (time.time() - ts) < self.ttl_seconds:
                return True
            else:
                del self._entries[cache_key]
        return False

    def mark_safe(self, cache_key: str) -> None:
        """Records a cache key as safe and persists atomically."""
        self._entries[cache_key] = time.time()
        self._save()

    def clear(self) -> None:
        """Clears all cached entries."""
        self._entries = {}
        if self.cache_path.exists():
            try:
                self.cache_path.unlink()
            except Exception:
                pass

    def _save(self) -> None:
        """Atomically saves cache to disk."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.cache_path.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._entries, f)
            temp_file.replace(self.cache_path)
        except Exception:
            # Non-fatal if cache write fails
            pass

    def __len__(self) -> int:
        return len(self._entries)

    def __bool__(self) -> bool:
        return True
