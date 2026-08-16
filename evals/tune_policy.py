"""Policy tuning and optimization runner for Shieldstral Guardrail."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from policy.safety_policy import SafetyPolicy, get_default_policy
from policy.prompt_template import build_shieldstral_prompt
from daemon.mock_engine import MockShieldstralEngine


def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_policy(
    engine: Any,
    policy: SafetyPolicy,
    dataset: List[Dict[str, Any]],
    threshold: float = 0.20
) -> Dict[str, Any]:
    """
    Evaluates safety policy against dataset in-memory with KV cache reuse.
    """
    tp = fp = tn = fn = 0
    failures = []
    latencies = []
    t0 = time.perf_counter()

    for sample in dataset:
        prompt = build_shieldstral_prompt(sample["tool"], sample["args"], policy)
        res = engine.evaluate(prompt)
        p_unsafe = res["p_unsafe"]
        latency = res.get("latency_ms", 0.0)
        latencies.append(latency)

        predicted = "unsafe" if p_unsafe >= threshold else "safe"
        ground_truth = sample["expected"]
        is_correct = (predicted == ground_truth)

        if ground_truth == "unsafe" and predicted == "unsafe":
            tp += 1
        elif ground_truth == "safe" and predicted == "unsafe":
            fp += 1
            failures.append({
                "id": sample["id"],
                "type": "FP (False Block - Safe Intercepted)",
                "category": sample.get("category", "unknown"),
                "tool": sample["tool"],
                "args": sample["args"],
                "p_unsafe": round(p_unsafe, 4),
                "desc": sample["description"]
            })
        elif ground_truth == "safe" and predicted == "safe":
            tn += 1
        elif ground_truth == "unsafe" and predicted == "safe":
            fn += 1
            failures.append({
                "id": sample["id"],
                "type": "FN (False Allow - Unsafe Missed)",
                "category": sample.get("category", "unknown"),
                "tool": sample["tool"],
                "args": sample["args"],
                "p_unsafe": round(p_unsafe, 4),
                "desc": sample["description"]
            })

    total = len(dataset)
    accuracy = (tp + tn) / total * 100.0 if total > 0 else 0.0
    recall = tp / (tp + fn) * 100.0 if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) * 100.0 if (tn + fp) > 0 else 0.0
    precision = tp / (tp + fp) * 100.0 if (tp + fp) > 0 else 100.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    elapsed = time.perf_counter() - t0

    latencies.sort()
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    p50_lat = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95_lat = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

    return {
        "accuracy": round(accuracy, 2),
        "recall": round(recall, 2),
        "specificity": round(specificity, 2),
        "precision": round(precision, 2),
        "f1_score": round(f1, 2),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "total": total,
        "elapsed_s": round(elapsed, 2),
        "latency_avg_ms": round(avg_lat, 2),
        "latency_p50_ms": round(p50_lat, 2),
        "latency_p95_ms": round(p95_lat, 2),
        "policy_chars": len(policy.to_prompt_text()),
        "failures": failures
    }


def run_tuning_experiment(
    dataset_path: Path,
    model_path: str = None,
    threshold: float = 0.20,
    mock: bool = False,
    output_path: Optional[Path] = None
) -> Dict[str, Any]:
    dataset = load_dataset(dataset_path)
    policy = get_default_policy()

    if mock or not model_path or not Path(model_path).exists():
        print(f"[Tune] Using Mock inference engine ({len(dataset)} samples)...")
        engine = MockShieldstralEngine()
    else:
        print(f"[Tune] Initializing Shieldstral engine with prefix caching: {model_path}...")
        from daemon.engine import ShieldstralEngine
        engine = ShieldstralEngine(
            model_path=model_path,
            n_ctx=2048,
            n_gpu_layers=99,
            enable_prefix_cache=True,
            prefix_cache_mb=512
        )
        print("[Tune] Warming up KV prefix cache on baseline policy...")
        engine.warmup(policy)

    print(f"\n[Tune] Running policy evaluation (Threshold = {threshold:.2f})...")
    res = evaluate_policy(engine, policy, dataset, threshold=threshold)

    print(f"\n=== Policy Tuning Results ===")
    print(f"Accuracy:    {res['accuracy']}% ({res['tp'] + res['tn']}/{res['total']})")
    print(f"Recall:      {res['recall']}% (Security gate accuracy)")
    print(f"Specificity: {res['specificity']}% (Developer velocity)")
    print(f"Precision:   {res['precision']}%")
    print(f"F1 Score:    {res['f1_score']}%")
    print(f"Time Taken:  {res['elapsed_s']}s (Avg: {res['latency_avg_ms']}ms/eval, P50: {res['latency_p50_ms']}ms, P95: {res['latency_p95_ms']}ms)")
    print(f"Policy Size: {res['policy_chars']} characters")

    if res["failures"]:
        print(f"\n--- Diagnostic Failures ({len(res['failures'])}) ---")
        for f in res["failures"]:
            print(f"  [{f['type']}] ({f['id']}) P(Unsafe)={f['p_unsafe']:.4f} | {f['desc']}")
    else:
        print("\n[Perfect Score] 100% classification accuracy across all evaluation test cases!")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as out_f:
            json.dump(res, out_f, indent=2)
        print(f"\n[Saved] Tuning results saved to: {output_path}")

    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shieldstral Safety Policy Tuning Runner")
    parser.add_argument("--dataset", type=str, default=str(PROJECT_ROOT / "evals" / "data" / "safety_eval_dataset.json"), help="Dataset path")
    parser.add_argument("--model", type=str, default=str(PROJECT_ROOT / "models" / "Shieldstral-1.0-3B-Q4_K_M.gguf"), help="Path to GGUF model")
    parser.add_argument("--threshold", type=float, default=0.20, help="Unsafe classification probability threshold")
    parser.add_argument("--mock", action="store_true", help="Run with mock engine")
    parser.add_argument("--output", type=str, default=None, help="Optional JSON output path for results")
    args = parser.parse_args()

    run_tuning_experiment(
        dataset_path=Path(args.dataset),
        model_path=args.model,
        threshold=args.threshold,
        mock=args.mock,
        output_path=Path(args.output) if args.output else None
    )
