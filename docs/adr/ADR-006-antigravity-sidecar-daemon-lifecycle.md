# ADR-006: Antigravity Sidecar Integration for Daemon Lifecycle Management

* **Status:** Accepted
* **Date:** 2026-08-15
* **Deciders:** Architecture Team

## Context and Problem Statement

The Shieldstral Guardrail Plugin relies on a resident local inference daemon (`127.0.0.1:8080`) to provide sub-60 ms single-token classifications. In ADR-001, we established that a resident background process is essential to avoid repeated 2–3 second cold-load latencies on every hook invocation.

However, operating the daemon as a detached external process spawned manually by the developer (`guardctl start --bg`) created operational friction:
1. Developers had to remember to start the daemon before launching Antigravity sessions.
2. If the daemon process crashed or exited, subsequent tool calls failed closed (`force_ask`), degrading user velocity until the developer noticed and manually restarted the daemon.
3. Managing multi-platform background process detachment (e.g. `DETACHED_PROCESS` on Windows vs. `start_new_session` on POSIX) was fragile.

## Decision Drivers

* **Zero Developer Friction:** Automatic startup when Antigravity launches, with zero manual terminal commands required.
* **Automatic Crash Recovery:** Guaranteed process resurrection if the inference engine crashes or is terminated.
* **Standardization:** Full alignment with Antigravity 2.0's native Customization and Sidecar framework.
* **Backward Compatibility:** Standalone execution via `guardctl` must remain available for CI/CD, manual evaluations, and benchmarking.

## Considered Options

1. **Keep Manual Background Process Spawning:** Continue relying on `python -m cli.guardctl start --bg` and developer memory.
2. **Spawn Ephemeral Daemon in PreToolUse Hook:** Launch daemon on the first tool execution from within `eval_guard.py`.
3. **Antigravity Native Sidecar (`sidecars/shieldstral-daemon`):** Package the daemon as a declarative Antigravity Sidecar managed by the Antigravity runtime.

## Decision Outcome

Chosen option: **Option 3: Antigravity Native Sidecar**.

### Rationale

* **Native Platform Lifecycle:** Antigravity discovers `sidecar.json` at `~/.gemini/config/plugins/agy-shieldstral-guard/sidecars/shieldstral-daemon/sidecar.json` and automatically launches the process alongside `agy`.
* **Automatic Healing:** With `"restart_policy": "always"`, Antigravity monitors the daemon PID and immediately restarts it upon unexpected termination.
* **Standardized Logging & Storage:** Antigravity isolates stdout/stderr logs in `~/.gemini/antigravity/sidecar_data/agy-shieldstral-guard/shieldstral-daemon/logs/` and exposes persistent data directories via `ANTIGRAVITY_EXECUTABLE_DATA_DIR`.
* **Clean Configuration Flow:** `scripts/install.py` registers `"agy-shieldstral-guard/shieldstral-daemon": {"enabled": true}` in `~/.gemini/config/config.json` upon plugin installation.

## Consequences

### Positive
* Developers experience seamless auto-approval on first launch without running separate terminal commands.
* High availability and crash recovery are handled natively by the Antigravity engine.
* Logging is standardized and accessible in the standard sidecar log directory.
* `guardctl` CLI continues to function seamlessly for manual testing and evaluation without conflict.

### Negative / Trade-offs
* Sidecar requires activation in `~/.gemini/config/config.json` (automated by `scripts/install.py`).
