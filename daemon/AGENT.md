# Daemon Layer Agent Guide (`daemon/AGENT.md`)

This document governs modifications, invariants, and operational guidelines for the **Inference Daemon & Engine Layer** located in `daemon/`.

---

## 🎯 Domain & Responsibilities

The Daemon Layer provides a long-lived, resident HTTP service that hosts the **Shieldstral 3B** model in VRAM/RAM. It performs single-token classification with logit normalization, eliminating per-invocation model loading latency.

### Key Files
* [`daemon/server.py`](./server.py): Multi-threaded HTTP server exposing `/health`, `/evaluate`, `/policy`, `/metrics`, and `/shutdown`.
* [`daemon/engine.py`](./engine.py): `llama-cpp-python` engine wrapper executing single-token forward passes and logprob extraction.
* [`daemon/mock_engine.py`](./mock_engine.py): High-speed deterministic mock engine for CI/CD, unit tests, and headless verification.
* [`daemon/__main__.py`](./__main__.py): Standalone CLI entrypoint for running `python -m daemon`.

---

## 🌐 HTTP API Specification

| Endpoint | Method | Input Payload | Output Payload | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | `GET` | None | `{"status": "healthy", "engine": "...", "model": "..."}` | Healthcheck and engine inspector |
| `/evaluate` | `POST` | `{"tool": "...", "args": {...}}` or `{"prompt": "..."}` | `{"p_unsafe": float, "is_safe": bool, "latency_ms": float, "top_logprobs": {...}}` | Primary classification endpoint |
| `/policy` | `GET` | None | `{"policy": "..."}` | Returns active safety policy text |
| `/metrics` | `GET` | None | `{"requests_total": int, "safe_count": int, "unsafe_count": int, "avg_latency_ms": float}` | Live performance metrics |
| `/shutdown` | `POST` | `{}` | `{"message": "Server shutting down..."}` | Graceful server shutdown |

---

## 🧮 Mathematical Classification Invariant

Inference MUST be performed in a **single forward pass** (`max_tokens=1`). Logprobs are extracted from candidate tokens and normalized:

$$P(\text{Unsafe}) = \frac{\sum_{t \in T_{\text{unsafe}}} e^{\text{logprob}(t)}}{\sum_{t \in T_{\text{unsafe}}} e^{\text{logprob}(t)} + \sum_{t \in T_{\text{safe}}} e^{\text{logprob}(t)}}$$

Where:
* $T_{\text{unsafe}} = \{\text{"Yes"}, \text{" Yes"}, \text{"yes"}, \text{"true"}, \text{"unsafe"}, \dots\}$
* $T_{\text{safe}} = \{\text{"No"}, \text{" No"}, \text{"no"}, \text{"false"}, \text{"safe"}, \dots\}$

---

## 🔒 Invariants for Agents

1. **`logits_all=True` Invariant:**
   * When initializing `llama_cpp.Llama`, `logits_all=True` MUST always be enabled to allow logprob extraction on completion tokens.
2. **`max_tokens=1` Constraint:**
   * Never generate multi-token text in production classification. Single-token logprob extraction delivers predictable 30–55 ms latency.
3. **Float32 Serialization Safety:**
   * Logprob dictionaries returned by `llama_cpp` may contain `numpy.float32` instances. Always convert them to native Python `float` before returning in responses to prevent JSON serialization errors.
4. **Thread-Safe Metrics:**
   * All mutations to the global `METRICS` dictionary in `server.py` MUST be guarded by `METRICS_LOCK`.
5. **No Eager Server Import in `daemon/__init__.py`:**
   * Keep `__init__.py` free of top-level `server.py` imports to avoid Python `runpy` package import race warnings when executing `python -m daemon`.

---

## 🧪 Verification & Testing

When modifying the Daemon Layer, run the following test suites:

```bash
# Test logit extraction and mathematical normalization
python -m unittest tests/test_math_and_logits.py

# Test daemon HTTP endpoints and server lifecycle
python -m unittest tests/test_daemon_server.py

# Run live benchmark against the daemon
python evals/run_evals.py --mock
```
