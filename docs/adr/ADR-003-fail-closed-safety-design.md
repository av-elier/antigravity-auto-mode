# ADR-003: Deterministic Fail-Closed Safety Design

* **Status:** Accepted
* **Date:** 2026-08-15
* **Deciders:** Architecture Team

## Context and Problem Statement

When an AI agent is executing in an autonomous or semi-autonomous environment, unexpected failures can occur in the guardrail pipeline (e.g., daemon offline, socket timeout, JSON decode error, out-of-memory exception).

A critical architectural decision is how the hook client responds when inference fails:
- **Fail-Open:** Allow the tool to execute automatically to preserve workflow velocity.
- **Fail-Closed:** Require manual human confirmation (`decision: "ask"` or exit code `1`) to prevent potentially catastrophic actions.

## Decision Drivers

* **Zero-Harm Guarantee:** A security guardrail must never permit an uninspected dangerous command (e.g. `rm -rf /`) because the daemon was restarted or timed out.
* **Developer Control:** When automated validation cannot verify safety, control must smoothly degrade to standard human confirmation.

## Decision Outcome

Chosen option: **Deterministic Fail-Closed Policy**.

Any error condition—including connection refused, socket timeouts, malformed payloads, or unmapped token predictions—immediately falls back to `decision: "ask"` and exits with code `1`.

### Behavior Matrix

| Scenario | Daemon Response | Hook Output (`stdout`) | Exit Code | Antigravity Action |
| :--- | :--- | :--- | :--- | :--- |
| **Safe action ($P < 0.20$)** | `{"p_unsafe": 0.01}` | `{"decision": "allow", ...}` | `0` | Auto-approved |
| **Unsafe action ($P \ge 0.20$)** | `{"p_unsafe": 0.85}` | `{"decision": "ask", ...}` | `1` | Prompts user confirmation |
| **Daemon offline / Crash** | Connection Refused | `{"decision": "ask", ...}` | `1` | Prompts user confirmation |
| **Inference Timeout (>2.0s)**| Socket Timeout | `{"decision": "ask", ...}` | `1` | Prompts user confirmation |
| **Malformed JSON stdin** | N/A | `{"decision": "ask", ...}` | `1` | Prompts user confirmation |

## Consequences

### Positive
* Complete safety guarantee: no destructive command can bypass security due to infrastructure failures.
* Graceful degradation: developers can continue working even if the daemon is stopped, simply confirming prompts manually.

### Negative / Trade-offs
* If the daemon is down, developers will experience confirmation prompts for all non-cached actions until the daemon is started.
