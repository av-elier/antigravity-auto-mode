# Scripts Layer Agent Guide (`scripts/AGENT.md`)

This document governs modifications, invariants, and operational guidelines for the **Automation & Lifecycle Scripts Layer** located in `scripts/`.

---

## 🎯 Domain & Responsibilities

The Scripts Layer provides standalone automation utilities for running the hook, downloading model weights, installing the plugin into Antigravity, and starting the daemon across different operating systems.

### Key Files
* [`scripts/eval_guard.py`](./eval_guard.py): Main hook script invoked by Antigravity CLI on tool execution.
* [`scripts/download_model.py`](./download_model.py): High-speed Hugging Face model weight downloader with `hf_transfer` support.
* [`scripts/install.py`](./install.py): Installer copying or linking plugin assets into `~/.gemini/config/plugins/` or `.agents/plugins/`.
* [`scripts/start_daemon.bat`](./start_daemon.bat): Windows launcher batch script.
* [`scripts/start_daemon.sh`](./start_daemon.sh): Linux/macOS launcher bash script.

---

## 🔒 Invariants for Agents

1. **`eval_guard.py` Zero-Dependency Requirement:**
   * `eval_guard.py` MUST be capable of running standalone using only the Python standard library, even if invoked outside a virtual environment.
2. **`models/` Directory Exclusion:**
   * Downloaded weights must be placed in `models/` (which is excluded in `.gitignore`) and NEVER committed to version control.
3. **Idempotent Installation (`install.py`):**
   * Running `install.py` repeatedly must overwrite existing files cleanly without leaving stale or corrupted assets.
4. **Cross-Platform Launcher Parity:**
   * Both `start_daemon.bat` and `start_daemon.sh` must accept additional CLI flags (e.g. `--port`, `--mock`, `--gpu-layers`) and pass them transparently to `python -m daemon`.
5. **Exit Code 0 Invariant:**
   * `eval_guard.py` must ALWAYS exit with status code `0` on all outcomes (allow, force_ask, fail-closed) so Antigravity 2.0 parses stdout JSON without crashing.

---

## 🧪 Verification & Testing

```bash
# Test download script help
python scripts/download_model.py --help

# Test install script dry-run / local mode
python scripts/install.py --local

# Test standalone hook script execution via stdin piping
echo '{"toolCall": {"name": "run_command", "args": {"CommandLine": "npm test"}}}' | python scripts/eval_guard.py
```
