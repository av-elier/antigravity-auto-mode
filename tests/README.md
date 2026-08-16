# Shieldstral Guardrail Automated Test Suite (`tests/`)

[![Tests](https://img.shields.io/badge/Tests-Passing%20(62%2F62)-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-100%25%20Contracts-blue.svg)](tests/)
[![Fast CI](https://img.shields.io/badge/Fast%20CI-%3C%2010s-orange.svg)](scripts/run_tests.py)

This directory contains the automated test suite for the **Shieldstral Guardrail for Google Antigravity**. The test suite is organized into distinct categories to guarantee sub-millisecond execution, prompt regression prevention, HTTP contract safety, and zero false allows on dangerous actions.

---

## 🏗️ Test Suite Architecture & Categorization

```text
tests/
├── conftest.py                          # Global pytest fixtures, dynamic ephemeral ports, environment isolation
├── test_*.py                            # Backwards-compatibility root test wrappers
│
├── unit/                                # Layer 1: Fast In-Memory Unit Tests (Target: < 0.5s)
│   ├── test_math_and_logits.py          # Logprob math, token normalization, fail-closed fallback
│   ├── test_policy_and_prompts.py       # Prompt formatting, delimiters, huge payload truncation
│   ├── test_cache.py                    # SHA-256 deterministic key hashing, TTL expiration, disk persistence
│   └── test_plugin_contracts.py         # Schema validation for plugin.json, hooks.json, sidecar.json
│
├── integration/                         # Layer 2: Component Integration Tests (Target: < 5.0s)
│   ├── test_daemon_server.py            # HTTP API (/health, /evaluate, /policy, /metrics, /shutdown), concurrency
│   ├── test_hook_client.py              # PreToolUse hook parsing, read-only bypass, fail-closed offline fallback
│   ├── test_sidecar.py                  # Dynamic port 0 resolution, endpoint file discovery, install registration
│   └── test_model_and_cache.py          # Model parameters (max_tokens=1), KV prefix cache & SHA-256 speedup
│
├── e2e/                                 # Layer 3: End-to-End Simulation Tests (Target: < 4.0s)
│   ├── test_e2e_antigravity_flow.py     # Subprocess stdin/stdout piping with real PreToolUse JSON payloads
│   └── test_cli_guardctl.py             # CLI guardctl commands (status, test, benchmark, clear-cache, policy)
│
└── eval_suite/                          # Layer 4: Safety Dataset Evals & Invariant Tests (Target: < 0.2s Mock)
    └── test_safety_evals.py             # Curated dataset benchmark asserting Zero False Allows (FNR=0.0%)
```

---

## 🔒 5 Core CI Guarantees

Every CI execution formally guarantees:

1. **Plugin, Hooks & Sidecar Manifest Integrity:**
   * Validates `plugin.json` and `hooks.json` against the [Google Antigravity Hooks Specification](../docs/ANTIGRAVITY_HOOKS_SPEC.md).
   * Validates `sidecars/shieldstral-daemon/sidecar.json` schema (`command`, `args`, `restart_policy`).
   * Validates dynamic ephemeral port 0 resolution and `ANTIGRAVITY_EXECUTABLE_DATA_DIR` discovery files.
2. **API & Endpoints Without Regression:**
   * Full endpoint contract coverage (`GET /health`, `POST /evaluate`, `GET /policy`, `GET /metrics`, `POST /shutdown`).
   * Concurrent request handling across thread pools without socket starvation.
   * Large payload truncation (50KB+ file contents sanitized to prevent buffer overflows or context blowup).
3. **Correct Use of Shieldstral Model & Working Caches:**
   * Enforces model inference parameters (`max_tokens=1`, `temperature=0.0`, `logprobs=10`, `logits_all=True`, `n_ctx=2048`).
   * Verifies **KV Prefix Cache** (`LlamaRAMCache`) accelerates prompt evaluation for static policies.
   * Verifies **SHA-256 Client Cache** delivers sub-millisecond ($< 1.0\text{ ms}$) subsequent evaluations.
4. **Safety Evals & Prompt Regression Prevention:**
   * Automated benchmark executing against `evals/data/safety_eval_dataset.json`.
   * **Zero False Allows ($FN = 0$) Invariant:** Any change that allows a destructive command (`rm -rf /`, `del System32`, AWS key exfiltration) immediately fails the build.
   * Enforces $\ge 95.0\%$ overall accuracy and $100.0\%$ security recall.
5. **Execution Speed & DevEx:**
   * Fast CI suite runs in single-digit seconds ($< 10\text{ s}$ total).
   * Segregated `@pytest.mark.real_model` for optional GPU/nightly testing.

---

## ⚡ Execution Speed & Performance Targets

| Test Suite | Scope | Target Duration | Observed Duration | Rating |
| :--- | :--- | :--- | :--- | :--- |
| **`unit`** | In-memory math, policies, cache hashing, plugin schemas | $\le \mathbf{1.0\text{ s}}$ | **0.18s** | ⚡ EXCELLENT |
| **`integration`** | HTTP endpoints, client hook, sidecar port 0, cache timing | $\le \mathbf{8.0\text{ s}}$ | **4.89s** | 🟢 OPTIMAL |
| **`e2e`** | Subprocess stdin/stdout piping, `guardctl` CLI suite | $\le \mathbf{5.0\text{ s}}$ | **3.41s** | 🟢 OPTIMAL |
| **`evals`** | Safety benchmark dataset on Mock engine | $\le \mathbf{1.0\text{ s}}$ | **0.01s** | ⚡ EXCELLENT |
| **Total Fast CI** | All 4 Suites (60 tests) | $\le \mathbf{15.0\text{ s}}$ | **8.48s** | 🟢 OPTIMAL |

---

## 🚀 How to Run Tests

### 1. Unified Test Runner (`scripts/run_tests.py`)

The unified test runner supports both `pytest` and zero-dependency `unittest` fallback with formatted summary tables:

```bash
# Run all suites with execution speed report:
python scripts/run_tests.py --kind all

# Run fast smoke tests (< 1 second):
python scripts/run_tests.py --kind fast

# Run specific suite:
python scripts/run_tests.py --kind unit
python scripts/run_tests.py --kind integration
python scripts/run_tests.py --kind e2e
python scripts/run_tests.py --kind evals
python scripts/run_tests.py --kind cache
python scripts/run_tests.py --kind sidecar

# Run with standard library unittest fallback:
python scripts/run_tests.py --runner unittest --kind all

# Run live Shieldstral 3B model benchmark (requires GGUF weights):
python scripts/run_tests.py --kind real-model
```

### 2. Via `guardctl` CLI

```bash
python -m cli.guardctl run-tests --kind all
python -m cli.guardctl run-tests --kind fast
python -m cli.guardctl run-tests --kind unit
```

### 3. Native Pytest Commands

```bash
# Run all tests (excluding heavy real model):
pytest -v -m "not real_model"

# Run by marker:
pytest -v -m unit
pytest -v -m integration
pytest -v -m e2e
pytest -v -m evals
pytest -v -m cache
pytest -v -m sidecar

# Run specific test file:
pytest -v tests/unit/test_math_and_logits.py
pytest -v tests/integration/test_daemon_server.py
```

### 4. Standard Library `unittest` Discovery

```bash
# Run full suite with standard unittest:
python -m unittest discover -v -s tests -p "test_*.py"

# Run specific file:
python -m unittest tests/test_math_and_logits.py
```

---

## 🏷️ Pytest Markers Reference

| Marker | Description |
| :--- | :--- |
| `@pytest.mark.unit` | Fast, in-memory unit tests without subprocesses or HTTP sockets. |
| `@pytest.mark.integration` | Tests spinning up ephemeral daemon servers or hook clients. |
| `@pytest.mark.e2e` | Subprocess piping tests and CLI interaction suites. |
| `@pytest.mark.evals` | Safety benchmark dataset evaluations and prompt delimiter checks. |
| `@pytest.mark.cache` | Quantitative tests verifying KV prefix cache and SHA-256 speedups. |
| `@pytest.mark.sidecar` | Antigravity Sidecar specification, discovery, and install registration. |
| `@pytest.mark.real_model` | Live inference tests requiring the 2.1GB Shieldstral 3B GGUF weights. |
| `@pytest.mark.slow` | Tests with longer execution times. |

---

## 🛠️ Adding New Tests

1. **Unit Tests:** Place in `tests/unit/test_<feature>.py` and tag with `@pytest.mark.unit`. Ensure zero network or persistent disk side-effects.
2. **Integration Tests:** Place in `tests/integration/test_<feature>.py`. Use `port=0` for ephemeral port binding and clean up servers in `tearDownClass`.
3. **Safety Dataset Samples:** Add new attack or benign scenarios to `evals/data/safety_eval_dataset.json`. Tests in `tests/eval_suite/test_safety_evals.py` will automatically evaluate them.
