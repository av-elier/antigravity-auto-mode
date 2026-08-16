# CLI Layer Agent Guide (`cli/AGENT.md`)

This document governs modifications, invariants, and operational guidelines for the **CLI Control Layer** located in `cli/`.

---

## 🎯 Domain & Responsibilities

The CLI Layer exposes the `guardctl` command-line utility used by developers and agents to manage the daemon process, inspect live metrics, run benchmarks, execute evaluations, and test specific tool actions.

### Key Files
* [`cli/guardctl.py`](./guardctl.py): Main CLI parser and command implementation.
* [`cli/__init__.py`](./__init__.py): Lazy package entrypoint.

---

## 🛠️ Command Specifications

| Command | Arguments | Action |
| :--- | :--- | :--- |
| `guardctl start` | `--model`, `--port`, `--host`, `--bg`, `--mock`, `--auto-download`, `--gpu-layers` | Launches inference daemon (foreground or detached background). Auto-downloads missing weights if needed. |
| `guardctl stop` | `--port`, `--host` | Sends POST `/shutdown` to terminate the daemon gracefully. |
| `guardctl status` | `--port`, `--host` | Queries `/health` and `/metrics` to display live server status and latency stats. |
| `guardctl logs` | `-n` / `--lines` | Displays formatted audit logs from recent hook executions. |
| `guardctl test` | `--tool`, `--args` | Tests evaluating a planned tool invocation through the full pipeline. |
| `guardctl benchmark`| `-n` (iterations) | Runs automated latency & throughput benchmark across safe and unsafe actions. |
| `guardctl eval` | `--dataset`, `--model`, `--daemon-url`, `--threshold`, `--mock`, `--output` | Runs safety benchmark on dataset and prints full metrics report. |
| `guardctl clear-cache` | None | Clears the local SHA-256 safe cache. |
| `guardctl policy` | None | Prints the active safety policy rules. |

---

## 🔒 Invariants for Agents

1. **Cross-Platform Process Detachment:**
   * On Windows: `guardctl start --bg` must resolve `pythonw.exe` and use `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` with detached stdio streams to prevent process termination when the parent terminal closes.
   * On Linux/macOS: Must use `start_new_session=True` with detached stdio streams.
2. **Auto-Download Safeguard:**
   * If a user or agent starts `guardctl start` without model weights and `--mock` is not set, the CLI must automatically invoke `download_hf_model()` rather than crashing with file-not-found.
3. **Graceful Shutdown Protocol:**
   * Always prefer communicating with the daemon's `/shutdown` HTTP endpoint rather than sending harsh SIGKILL signals.
4. **Lazy Entrypoint in `cli/__init__.py`:**
   * `cli/__init__.py` must not eagerly import `guardctl` at module level to prevent `runpy` module warning when executing `python -m cli.guardctl`.

---

## 🧪 Verification & Testing

When modifying the CLI Layer, test CLI commands locally:

```bash
# Verify policy inspection
python -m cli.guardctl policy

# Verify status report
python -m cli.guardctl status

# Verify single tool testing
python -m cli.guardctl test --tool run_command --args '{"CommandLine": "npm test"}'

# Verify benchmark execution
python -m cli.guardctl benchmark -n 20
```
