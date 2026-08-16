# Client Layer Agent Guide (`client/AGENT.md`)

This document governs modifications, invariants, and operational guidelines for the **Hook Client & Cache Layer** located in `client/` and `scripts/eval_guard.py`.

---

## 🎯 Domain & Responsibilities

The Client Layer is responsible for executing inside the Antigravity CLI's process space on every tool call. It acts as the high-speed decision gate that either auto-approves safe actions or falls back to user confirmation.

### Key Files
* [`client/eval_client.py`](./eval_client.py): Core evaluation pipeline, configuration loader, environment variable resolution, and fail-closed handling.
* [`client/cache.py`](./cache.py): SHA-256 read-through cache with atomic persistence and TTL validation.
* [`scripts/eval_guard.py`](../scripts/eval_guard.py): Zero-dependency standalone hook entrypoint invoked by Antigravity.

---

## ⚡ Execution Pipeline & Fast Paths

```mermaid
flowchart TD
    Stdin[Antigravity Stdin JSON] --> Parser[Parse toolCall / raw JSON]
    Parser --> KeyGen[Compute SHA-256 Digest]
    KeyGen --> CacheCheck{Cache is_safe?}
    CacheCheck -->|Yes: < 2ms| Allow1["decision: allow (Cached)"]
    
    CacheCheck -->|No: Miss| DaemonReq[POST http://127.0.0.1:8080/evaluate]
    DaemonReq --> ResponseCheck{P(Unsafe) < 0.20?}
    ResponseCheck -->|Yes: Safe| CacheWrite[Mark Cache Safe]
    CacheWrite --> Allow2["decision: allow (Auto-Approved)"]
    
    ResponseCheck -->|No: Unsafe / Secret Access| ForceAsk1["decision: force_ask (Active Interception)"]
    Daemon -.->|Timeout / Connection Refused| FailClosed["Fail-Closed: decision: force_ask"]
```

---

## 🔒 Invariants for Agents

1. **Zero External Dependencies (Strict NFR-3):**
   * Under NO circumstances may third-party imports (e.g. `requests`, `pydantic`, `torch`, `transformers`) be added to `client/` or `scripts/eval_guard.py`.
   * Only use standard library modules: `urllib.request`, `urllib.error`, `json`, `hashlib`, `os`, `sys`, `pathlib`, `time`.
2. **Sub-15ms Process Startup:**
   * Keep module-level code minimal. Defer optional work until needed.
3. **Deterministic Fail-Closed Fallback (FR-3):**
   * Any network failure, socket timeout, malformed JSON, or unhandled exception MUST return `{"decision": "force_ask", "reason": "..."}` and exit with code `0`.
4. **Universal Exit Code 0 (Antigravity 2.0 Invariant):**
   * All execution paths (`run_hook`) must terminate cleanly with exit code `0`. Non-zero exit codes cause Antigravity 2.0 to discard stdout JSON output.
5. **Atomic Cache Writes (FR-4):**
   * Disk persistence in `GuardCache` must always write to a temporary file (`.tmp`) and use `Path.replace()` to prevent race conditions during concurrent tool executions.
6. **Deterministic Argument Hashing:**
   * Argument dictionaries must be serialized with `json.dumps(args, sort_keys=True, separators=(",", ":"))` before SHA-256 hashing.
7. **Structured Audit Logging:**
   * Invocations must record structured metadata (timestamp, conversation ID, tool, action, decision, p_unsafe, latency) with automatic 5MB log rotation.

---

## 🧪 Verification & Testing

When modifying the Client Layer, run the following test suites:

```bash
# Test cache hashing, persistence, and TTL
python -m unittest tests/test_cache.py

# Test client evaluation logic, read-only fast paths, and fail-closed handling
python -m unittest tests/test_hook_client.py

# Test end-to-end Antigravity stdin/stdout simulation
python -m unittest tests/test_e2e_antigravity_flow.py
```
