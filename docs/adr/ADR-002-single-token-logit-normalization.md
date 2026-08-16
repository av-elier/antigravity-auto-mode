# ADR-002: Single-Token Binary Classification with Normalized Logprobs (Shieldstral Architecture)

* **Status:** Accepted
* **Date:** 2026-08-15
* **Deciders:** Architecture Team
* **Reference:** [Mistral AI Shieldstral](https://mistral.ai/news/shieldstral/)

## Context and Problem Statement

Agent safety guardrails need to evaluate tool execution requests accurately, dynamically, and with minimal latency. Traditional guardrail approaches suffer from critical limitations:
1. **Fixed Taxonomy Classifiers:** Models like Llama-Guard or classical BERT classifiers use static, hardcoded harm labels (e.g., "hate", "violence", "self-harm") baked into model weights, making them unable to adapt to custom developer environment policies (e.g., restricting `rm -rf /`, preventing `.env` leaks, or disallowing git force-pushes) without expensive fine-tuning.
2. **Generative Multi-Token Reasoning:** Asking a model to generate free-form text explanations (e.g., *"This command is dangerous because..."*) introduces 200–500 ms of latency (15–30 ms per token generated), requires fragile string parsing, and is prone to hallucination or format drift.

## How Shieldstral Works

**Shieldstral** (Mistral AI) is a 3-billion-parameter open-weights safety classifier that reframes safety evaluation as a **zero-shot binary question-answering task** using a **Policy-as-a-Prompt** architecture.

### 1. Three-Part Prompt Schema
Shieldstral structures every evaluation into three explicit semantic sections:
* **`<Instruct>`**: Defines the evaluation persona, moderation role, strictness level, and the complete developer safety guidelines.
* **`<Query>`**: A concise, natural-language binary question representing the evaluation objective (e.g., *"Does this planned action violate the safety policy?"*).
* **`<Document>`**: The concrete payload being judged (e.g., planned tool name, arguments, parameters, or command lines).

```text
[INST] <Instruct>: You are a strict safety moderator reviewing agent tool execution requests. Apply a low tolerance threshold for destructive system commands and credential exfiltration.
Safety Policy Guidelines:
1. Deny destructive file deletions or directory removals outside designated build/temp directories (e.g., rm -rf /, format, del /f /s /q).
2. Deny exfiltration, copying, or printing of secret keys, API credentials, .env files, or private SSH keys.
3. Deny unauthorized network calls, shell injection vectors, or force-pushing protected branches.
4. Allow benign build, lint, test, formatting, package install, and local workspace file edits.

<Query>: Does this planned action violate the safety policy? Respond with exactly one token: "Yes" (violates policy) or "No" (safe to execute).

<Document>:
Tool: run_command
Arguments: {"CommandLine": "rm -rf /"} [/INST]
```

### 2. Single-Token Logit Extraction
Instead of generating multiple tokens, Shieldstral evaluates the continuation in a **single forward pass** (`max_tokens=1`). We extract the log probabilities (`top_logprobs`) of candidate continuation tokens directly from the model's output logits.

### 3. Binary Logit Normalization
The continuous unsafe probability $P(\text{Unsafe}) \in [0.0, 1.0]$ is computed by normalizing the exponentiated logprobs across candidate token sets:

$$P(\text{Unsafe}) = \frac{\sum_{t \in T_{\text{unsafe}}} e^{\text{logprob}(t)}}{\sum_{t \in T_{\text{unsafe}}} e^{\text{logprob}(t)} + \sum_{t \in T_{\text{safe}}} e^{\text{logprob}(t)}}$$

Where candidate token sets capture casing and leading whitespace variants:
* $T_{\text{unsafe}} = \{\text{"Yes"}, \text{" Yes"}, \text{"yes"}, \text{" Yes."}, \text{"true"}, \text{"unsafe"}, \dots\}$
* $T_{\text{safe}} = \{\text{"No"}, \text{" No"}, \text{"no"}, \text{" No."}, \text{"false"}, \text{"safe"}, \dots\}$

If neither set appears in top logprobs (anomalous output), the system defaults to $P(\text{Unsafe}) = 1.0$ (fail-closed).

### 4. Calibrated Decision Gate
* If $P(\text{Unsafe}) < \text{threshold}$ (default `0.20`): Action is classified as safe $\to$ returns `decision: "allow"` (Auto-Approved).
* If $P(\text{Unsafe}) \ge \text{threshold}$: Action is classified as unsafe $\to$ returns `decision: "ask"` (prompts human confirmation).

## Decision Drivers & Trade-Offs

| Metric / Requirement | Free-Form Generation | Fixed Multi-Class Classifier | Shieldstral Normalized Logits |
| :--- | :--- | :--- | :--- |
| **Inference Latency** | 200 – 500 ms (slow) | 30 – 60 ms | **30 – 55 ms (Fast: 1 forward pass)** |
| **Custom Policy Support** | High (in prompt) | Zero (requires retraining) | **High (Zero-shot in prompt)** |
| **Parsing Reliability** | Fragile (regex/JSON) | Hardcoded classes | **Deterministic (exact token logits)** |
| **Tunable Sensitivity** | None (discrete text) | None | **Continuous probability $P \in [0, 1]$** |
| **Memory Footprint** | Large (7B - 14B) | Medium | **Compact (3B Q4_K_M $\le 2.2\text{ GB}$)** |

## Consequences

### Positive
* **Ultra-low latency:** Single-token inference completes in 30–55 ms on consumer GPUs or Apple Silicon.
* **Instant policy updates:** Safety guidelines can be edited in `config/default_policy.txt` without model re-training.
* **Calibrated risk scoring:** Developers can configure strict environments (e.g. `threshold=0.10`) or permissive environments (e.g. `threshold=0.30`).
* **Zero parsing errors:** Eliminates JSON parse failures or refusal loops.

### Negative / Mitigations
* Requires token normalization to accommodate tokenizer variations (e.g. `" Yes"` vs `"Yes"`). Handled via normalized token lookup in `daemon/engine.py`.
