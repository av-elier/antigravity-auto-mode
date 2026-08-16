# Tests Layer Agent Guide (`tests/AGENT.md`)

This document governs modifications, invariants, and operational guidelines for the **Automated Test Suite** located in `tests/`.

---

## 🎯 Domain & Responsibilities

The Tests Layer provides continuous automated verification across all system components, ensuring that math calculations, caching logic, HTTP APIs, hook client contracts, sidecar lifecycles, and safety policies function without regressions.

### Categorized Test Architecture

| Directory / File | Category | Target Component | Scope & Verifications |
| :--- | :--- | :--- | :--- |
| [`tests/unit/test_math_and_logits.py`](./unit/test_math_and_logits.py) | `unit` | `daemon/engine.py` | Token normalization, binary logprob extraction, ambiguous distributions, fail-closed fallback when tokens missing. |
| [`tests/unit/test_policy_and_prompts.py`](./unit/test_policy_and_prompts.py) | `unit` | `policy/` | Policy text rendering, dynamic rule additions, `<Instruct>/<Query>/<Document>` delimiters, payload sanitization. |
| [`tests/unit/test_cache.py`](./unit/test_cache.py) | `unit` | `client/cache.py` | Deterministic SHA-256 key generation with sorted args, cache hit/miss, atomic file saving, TTL expiration, cache clearing. |
| [`tests/unit/test_plugin_contracts.py`](./unit/test_plugin_contracts.py) | `unit` | Root Manifests | Validates `plugin.json`, `hooks.json`, and `sidecar.json` against Google Antigravity specifications. |
| [`tests/integration/test_daemon_server.py`](./integration/test_daemon_server.py) | `integration` | `daemon/server.py` | HTTP endpoints (`/health`, `/evaluate`, `/policy`, `/metrics`, `/shutdown`), request metrics tracking, concurrency. |
| [`tests/integration/test_hook_client.py`](./integration/test_hook_client.py) | `integration` | `client/eval_client.py` | Antigravity `PreToolUse` JSON parsing, read-only fast paths, cache hit paths, dynamic endpoint discovery, fail-closed handling. |
| [`tests/integration/test_sidecar.py`](./integration/test_sidecar.py) | `integration` | `sidecars/` & `scripts/install.py` | Sidecar JSON schema validation, dynamic port 0 resolution, endpoint discovery file creation/cleanup, and install registration. |
| [`tests/integration/test_model_and_cache.py`](./integration/test_model_and_cache.py) | `integration` | `daemon/engine.py` & `client/cache.py` | Model parameters (`max_tokens=1`), quantitative KV prefix cache acceleration, SHA-256 cache latency measurement. |
| [`tests/e2e/test_e2e_antigravity_flow.py`](./e2e/test_e2e_antigravity_flow.py) | `e2e` | Full Subprocess Hook | End-to-end simulation executing `eval_guard.py` subprocess with stdin/stdout piping across safe and unsafe commands. |
| [`tests/e2e/test_cli_guardctl.py`](./e2e/test_cli_guardctl.py) | `e2e` | `cli/guardctl.py` | End-to-end validation of all `guardctl` CLI commands (`status`, `test`, `benchmark`, `clear-cache`, `logs`, `eval`). |
| [`tests/eval_suite/test_safety_evals.py`](./eval_suite/test_safety_evals.py) | `evals` | Dataset Benchmark | Evaluates dataset benchmark asserting **Zero False Allows ($FN = 0$)** on destructive actions and prompt invariants. |

---

## 🔒 Invariants for Agents

1. **Zero False Allows ($FN = 0$) on Destructive Actions:**
   * Any change that allows a destructive tool call (`rm -rf /`, credential exfiltration, netcat backdoors, git force push) MUST be rejected.
2. **Fast CI Execution ($< 10\text{ s}$ Total):**
   * Standard unit, integration, e2e, and mock eval suites MUST complete in $< 10\text{ seconds}$ total.
   * Real model GGUF inference tests MUST be gated under `@pytest.mark.real_model` and `RUN_REAL_MODEL=1`.
3. **Dynamic Ephemeral Port Allocation (Port 0):**
   * Integration tests spinning up background test servers MUST pass `port=0` to avoid port conflicts with running daemons.
4. **Deterministic Cleanup:**
   * Temporary files, cache directories, and server sockets MUST be closed and deleted in `tearDown()` / `tearDownClass()`.
5. **Standard Library Hook Independence:**
   * The hook script (`scripts/eval_guard.py`) MUST depend ONLY on the Python 3 standard library.

---

## 🧪 Running Test Suites

```bash
# Run all suites via unified test runner:
python scripts/run_tests.py --kind all

# Run fast smoke test (< 1s):
python scripts/run_tests.py --kind fast

# Run via guardctl CLI:
python -m cli.guardctl run-tests --kind all

# Run specific category via pytest:
pytest -v -m unit
pytest -v -m integration
pytest -v -m e2e
pytest -v -m evals

# Run standard library unittest discovery:
python -m unittest discover -v -s tests -p "test_*.py"
```
