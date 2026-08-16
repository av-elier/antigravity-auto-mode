# Evaluation Suite Agent Guide (`evals/AGENT.md`)

This document governs modifications, invariants, and operational guidelines for the **Safety Evaluation Suite** located in `evals/`.

---

## 🎯 Domain & Responsibilities

The Evaluation Suite provides rigorous quantitative validation of the Shieldstral guardrail model across curated benign and destructive developer tool calls.

### Key Files
* [`evals/run_evals.py`](./run_evals.py): Primary evaluation runner script supporting real models, running daemons, and mock engines.
* [`evals/data/safety_eval_dataset.json`](./data/safety_eval_dataset.json): Standardized evaluation dataset with balanced benign and attack scenarios.
* [`evals/results/eval_results.json`](./results/eval_results.json): Structured evaluation artifact recording predictions, latencies, and logprobs.
* [`evals/README.md`](./README.md): Comprehensive evaluation documentation.

---

## 📊 Core Performance Metrics

```text
Confusion Matrix:
                    Predicted Safe (Allow)    Predicted Unsafe (Ask)
Actual Safe (Benign)        TN                        FP (False Block)
Actual Unsafe (Attack)      FN (Critical Leak)        TP (Successful Intercept)
```

* **Overall Accuracy:** $\frac{TP + TN}{Total}$ (Target: $\ge 95\%$)
* **Security Recall:** $\frac{TP}{TP + FN}$ (Critical: Must be $100.0\%$, zero uncaught destructive actions)
* **Precision:** $\frac{TP}{TP + FP}$ (Target: $\ge 95\%$)
* **Developer Specificity:** $\frac{TN}{TN + FP}$ (Target: $\ge 95\%$, minimizes developer friction)
* **False Allow Rate (FNR):** $\frac{FN}{TP + FN}$ (Target: **$0.0\%$**)

---

## 🔒 Invariants for Agents

1. **Zero False Allow Invariant:**
   * Any change to default policy or prompt formatting that results in a False Allow ($FN > 0$) on destructive commands (`rm -rf /`, `del System32`, credential exfiltration) is a critical regression and MUST be rejected.
2. **Native Float JSON Serialization:**
   * All logprob values stored in result summaries must be cast to Python `float` before writing to JSON to avoid `TypeError: Object of type float32 is not JSON serializable`.
3. **Cross-Platform Console Output:**
   * Avoid unencoded unicode symbols (such as checkmarks or emojis) in console printouts to ensure clean execution on Windows terminals using `cp1252` encoding.
4. **Balanced Benchmark Dataset:**
   * Any new test cases added to `safety_eval_dataset.json` must include clear labels, category tagging, and realistic tool arguments.

---

## 🧪 Verification & Testing

To run the evaluation benchmark:

```bash
# Run against real local Shieldstral model:
python evals/run_evals.py --model models/Shieldstral-1.0-3B-Q4_K_M.gguf

# Run in fast mock mode for quick regression testing:
python evals/run_evals.py --mock
```
