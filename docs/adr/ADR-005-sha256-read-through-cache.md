# ADR-005: SHA-256 Read-Through Caching for Deterministic Safe Invocations

* **Status:** Accepted
* **Date:** 2026-08-15
* **Deciders:** Architecture Team

## Context and Problem Statement

Agents frequently repeat common deterministic operations (e.g. `npm test`, `pytest`, `git status`, `cargo check`). While inference on local Shieldstral is fast (30–55 ms), repeated checks across dozens of steps accumulate unnecessary GPU/CPU cycles and latency.

## Decision Drivers

* **Sub-Millisecond Fast Path:** Cache hits must return in $< 3\text{ ms}$.
* **Concurrency Safety:** Parallel tool executions or hook invocations must not corrupt the cache file.
* **Deterministic Hashing:** Tool name and arguments must produce identical hashes regardless of dictionary key ordering.

## Decision Outcome

Chosen option: **Deterministic SHA-256 Digest Read-Through Caching**.

### Hashing Mechanism
1. Tool arguments are normalized into sorted-key JSON: `json.dumps(args, sort_keys=True, separators=(",", ":"))`.
2. The hash key is computed as:
   $$\text{Key} = \text{SHA256}(\text{tool\_name} + \text{":"} + \text{normalized\_args\_str})$$
3. When the daemon classifies an action as safe ($P(\text{Unsafe}) < 0.20$), the SHA-256 digest is recorded in the local cache with a timestamp.
4. Subsequent identical tool invocations match the cache key and return `decision: "allow"` within $< 2\text{ ms}$ without querying the daemon.
5. Disk persistence uses atomic file replacement (`tempfile.replace()`) to prevent race conditions.

## Consequences

### Positive
* Cache hit latency is reduced to ~1–2 ms (100x faster than model inference).
* Substantially reduces power consumption and VRAM compute utilization.
* Cache entries automatically expire after TTL (default 24 hours).

### Negative / Trade-offs
* Only safe actions are cached (unsafe actions are always re-evaluated by the model on every invocation).
