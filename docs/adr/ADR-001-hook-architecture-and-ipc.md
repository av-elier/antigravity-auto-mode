# ADR-001: Standalone Background Daemon vs. In-Process Model Loading

* **Status:** Accepted
* **Date:** 2026-08-15
* **Deciders:** Architecture Team

## Context and Problem Statement

Antigravity executes the `PreToolUse` lifecycle hook before running any agent tool. For this guardrail to be practical during active developer coding sessions, the hook execution latency must remain under 100 ms (NFR-1).

Loading the 3B-parameter quantized Shieldstral GGUF model (approx. 2.2 GB) from disk into memory and initializing GPU/VRAM context on every hook execution takes between 1,500 ms and 3,500 ms. If the hook were to load the model in-process for each tool execution, every single action performed by the agent would freeze the developer experience for several seconds.

## Decision Drivers

* **Latency Budget (NFR-1):** Total uncached hook overhead must be $\le 100\text{ ms}$.
* **Simplicity:** Minimal architectural overhead, easy local deployment for individual developers.
* **Resilience:** If the daemon becomes unavailable, the agent loop must not crash.

## Considered Options

1. **In-Process Ephemeral Model Loading:** Load GGUF model inside `eval_guard.py` on each hook call.
2. **In-CLI Engine Modification:** Embed model inference directly into the compiled `agy` binary.
3. **Standalone Background Daemon (Local HTTP / UDS):** Keep a long-lived Python daemon resident in memory/VRAM and query it from a lightweight client via loopback HTTP (`127.0.0.1:8080`).

## Decision Outcome

Chosen option: **Option 3: Standalone Background Daemon**.

### Rationale

* **Cold-load elimination:** With the model resident in VRAM, a single-token forward pass takes 30–55 ms.
* **Zero changes to core CLI binary:** Hooks communicate cleanly through the standard `PreToolUse` contract.
* **Cross-platform support:** Standard loopback HTTP runs identically across Windows, macOS, and Linux without platform-specific socket quirks.

## Consequences

### Positive
* Hook latency drops from >2,000 ms to <60 ms uncached.
* Clean separation of concerns between client hook and model inference engine.
* Developers can restart or reconfigure the daemon without interrupting the CLI.
* Fully adheres to the official [Antigravity Lifecycle Hooks Specification](../ANTIGRAVITY_HOOKS_SPEC.md), including active safety interception ('allow' / 'force_ask') and clean exit code 0 handling.

### Negative / Trade-offs
* Requires a running background process (`guardctl start --bg`).
* Managed via deterministic fail-closed fallback (ADR-003) if the daemon is offline.

