# Sidecar Subsystem Agent Guide (`sidecars/shieldstral-daemon/AGENT.md`)

This document governs modifications, invariants, and operational guidelines for the **Antigravity Sidecar Subsystem** located in `sidecars/shieldstral-daemon/`.

---

## 🎯 Domain & Responsibilities

The Sidecar Subsystem configures and runs the **Shieldstral 3B inference daemon** as a managed background service directly under the Antigravity runtime, conforming to the [Antigravity Sidecar Specification](https://antigravity.google/docs/sidecars/).

### Key Files
* [`sidecars/shieldstral-daemon/sidecar.json`](./sidecar.json): Declarative sidecar configuration conforming to Antigravity schema (`command`, `args`, `restart_policy`, `display_name`, `description`).
* [`sidecars/shieldstral-daemon/run_daemon.py`](./run_daemon.py): Main entrypoint script launched by Antigravity; handles plugin root resolution, config discovery, automatic model downloading, and server initialization.
* [`sidecars/shieldstral-daemon/AGENT.md`](./AGENT.md): This architectural and operational specification.

---

## ⚙️ Antigravity Sidecar Lifecycle Integration

### Discovery & Naming
* **Discovery Location:** When installed as a plugin, discovered at `~/.gemini/config/plugins/antigravity-auto-mode/sidecars/shieldstral-daemon/sidecar.json`.
* **Sidecar ID:** `antigravity-auto-mode/shieldstral-daemon` (formed as `<pluginName>/<sidecarName>`).
* **Current Working Directory (CWD):** The sidecar directory acts as the working directory during execution.

### User Activation in `~/.gemini/config/config.json`
Sidecars in Antigravity are disabled by default until explicitly enabled in global user config:
```json
{
  "sidecars": {
    "antigravity-auto-mode/shieldstral-daemon": {
      "enabled": true
    }
  }
}
```

### Runtime Environment & Logging
* **Logs:** Antigravity routes stdout and stderr streams to `~/.gemini/antigravity/sidecar_data/<sidecarId>/logs/`.
* **Persistent Data:** Antigravity provides the environment variable `ANTIGRAVITY_EXECUTABLE_DATA_DIR` pointing to `~/.gemini/antigravity/sidecar_data/<sidecarId>/data/`.
* **Restart Policy:** Configured to `"always"` so crashes or unexpected exits trigger immediate automatic daemon resurrection without agent failure.

---

## 🔒 Invariants for Agents

1. **Schema Integrity in `sidecar.json`:**
   * `command` and `builtin` are mutually exclusive. Use `"command": "python"` and `"args": ["run_daemon.py"]`.
   * `restart_policy` MUST be one of `"always"`, `"on-failure"`, or `"never"`. Production default is `"always"`.
2. **CWD Independence:**
   * `run_daemon.py` MUST resolve the plugin root relative to `__file__` (parent's parent of `sidecars/shieldstral-daemon`) to ensure imports (`client`, `daemon`, `policy`, `scripts`) succeed regardless of CWD.
3. **Graceful Signal Handling:**
   * `run_daemon.py` must register SIGINT and SIGTERM handlers to permit Antigravity to terminate the sidecar gracefully when shutting down.
4. **Resilient Auto-Download & Fallback:**
   * If model weights are missing and internet access is unavailable during test suites, `run_daemon.py` gracefully logs a warning and falls back to `--mock` rather than crashing in an unrecoverable loop.

---

## 🧪 Verification & Testing

```bash
# Validate sidecar schema and launcher logic
python -m unittest tests/test_sidecar.py

# Run all test suites
python -m unittest discover -v -s tests -p "test_*.py"
```
