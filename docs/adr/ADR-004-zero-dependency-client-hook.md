# ADR-004: Zero-Dependency Client Hook Implementation

* **Status:** Accepted
* **Date:** 2026-08-15
* **Deciders:** Architecture Team

## Context and Problem Statement

Antigravity invokes the `scripts/eval_guard.py` hook on every tool execution. In high-frequency workflows (e.g. running multiple automated steps, grepping files, creating directories), the overhead of importing heavy Python packages (such as `requests`, `torch`, `transformers`, `pydantic`) can consume 100–300 ms just during Python process startup and import resolution.

Furthermore, requiring third-party libraries in the global Python environment creates installation friction and version conflict risks.

## Decision Drivers

* **Process Startup Latency:** Hook execution startup must complete in $< 15\text{ ms}$.
* **Zero Installation Hassle:** The hook script must run out-of-the-box on vanilla Python 3.8+.
* **Portability:** Seamless execution on Linux, macOS, and Windows.

## Decision Outcome

Chosen option: **Zero External Dependencies for the Hook Client**.

`scripts/eval_guard.py` and `client/` rely exclusively on Python standard library modules:
- `urllib.request` / `urllib.error` for loopback HTTP transport.
- `json` for input/output payload encoding and parsing.
- `hashlib` for SHA-256 digest calculation.
- `pathlib` & `os` for filesystem paths and atomic cache writes.
- `time` & `sys` for timing and I/O streams.

## Consequences

### Positive
* Process startup overhead is reduced to ~10–12 ms.
* The plugin can be dropped into `.agents/plugins/` without running `pip install` in the user's base environment.
* High reliability and immunity to third-party dependency breakage.

### Negative / Trade-offs
* Heavy ML libraries (`llama-cpp-python`) are isolated exclusively to the standalone daemon environment.
