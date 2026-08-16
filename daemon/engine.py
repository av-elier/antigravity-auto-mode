"""Inference engine for Shieldstral using llama-cpp-python."""
import math
import time
from typing import Dict, Any, Tuple, Optional, Set

SAFE_TOKENS: Set[str] = {"no", " no", "false", " safe", "safe", "no.", " no."}
UNSAFE_TOKENS: Set[str] = {"yes", " yes", "true", " unsafe", "unsafe", "yes.", " yes."}


def normalize_token(token: str) -> str:
    """Standardizes token strings for matching."""
    return token.strip().lower().rstrip(".,;:!?")


def compute_unsafe_probability(
    top_logprobs: Dict[str, float],
    safe_tokens: Optional[Set[str]] = None,
    unsafe_tokens: Optional[Set[str]] = None
) -> Tuple[float, float, float]:
    """
    Calculates the normalized probability of Unsafe from the top logprobs.
    
    Formula:
        P(Unsafe) = sum(exp(lp) for unsafe) / (sum(exp(lp) for unsafe) + sum(exp(lp) for safe))
        
    Returns:
        Tuple of (p_unsafe, sum_p_safe, sum_p_unsafe).
        Defaults to (1.0, 0.0, 0.0) if neither token set is found.
    """
    if safe_tokens is None:
        safe_tokens = SAFE_TOKENS
    if unsafe_tokens is None:
        unsafe_tokens = UNSAFE_TOKENS

    p_safe = 0.0
    p_unsafe = 0.0

    for tok, lp in top_logprobs.items():
        norm_tok = normalize_token(tok)
        raw_tok_lower = tok.lower()
        
        prob = math.exp(lp)
        if norm_tok in safe_tokens or raw_tok_lower in safe_tokens:
            p_safe += prob
        elif norm_tok in unsafe_tokens or raw_tok_lower in unsafe_tokens:
            p_unsafe += prob

    total = p_safe + p_unsafe
    if total > 0.0:
        p_unsafe_norm = p_unsafe / total
    else:
        # If neither safe nor unsafe token appears, fail-closed to unsafe
        p_unsafe_norm = 1.0

    return p_unsafe_norm, p_safe, p_unsafe


class ShieldstralEngine:
    """Wraps llama_cpp Llama model for fast single-token safety classification with prefix KV caching."""

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_gpu_layers: int = 99,
        enable_prefix_cache: bool = True,
        prefix_cache_mb: int = 512,
        n_threads: Optional[int] = None,
        n_batch: int = 512,
        verbose: bool = False
    ):
        try:
            import os
            from llama_cpp import Llama, LlamaRAMCache
        except ImportError as e:
            raise ImportError(
                "llama-cpp-python is required to run the real Shieldstral engine. "
                "Install it via 'pip install llama-cpp-python' or run in mock mode."
            ) from e

        if n_threads is None:
            n_threads = max(1, (os.cpu_count() or 4) - 1)

        self.model_path = model_path
        self.enable_prefix_cache = enable_prefix_cache
        self.prefix_cache_mb = prefix_cache_mb
        self.cache = None

        # llama-cpp requires logits_all=True to extract completion logprobs
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_threads=n_threads,
            n_batch=n_batch,
            logits_all=True,
            verbose=verbose
        )

        if self.enable_prefix_cache:
            try:
                self.cache = LlamaRAMCache(capacity_bytes=prefix_cache_mb * 1024 * 1024)
                self.llm.set_cache(self.cache)
            except Exception as ce:
                if verbose:
                    print(f"[Warning] Failed to initialize LlamaRAMCache: {ce}")
                self.cache = None

    def warmup(self, policy: Optional[Any] = None) -> float:
        """
        Executes a warmup evaluation on the static prompt prefix.
        Pre-populates the KV cache so subsequent live tool evaluations have zero prefill delay.
        """
        start_time = time.perf_counter()
        from policy.prompt_template import build_shieldstral_prompt
        dummy_prompt = build_shieldstral_prompt("warmup", {"CommandLine": "echo init"}, policy)
        try:
            self.evaluate(dummy_prompt)
        except Exception:
            pass
        return (time.perf_counter() - start_time) * 1000.0

    def evaluate(self, prompt: str) -> Dict[str, Any]:
        """
        Executes a single forward pass and returns classification probabilities.
        """
        start_time = time.perf_counter()

        output = self.llm(
            prompt,
            max_tokens=1,
            temperature=0.0,
            logprobs=10
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        choices = output.get("choices", [])
        if not choices:
            return {
                "p_unsafe": 1.0,
                "is_safe": False,
                "latency_ms": latency_ms,
                "error": "Empty choices from model"
            }

        raw_top_logprobs = choices[0].get("logprobs", {}).get("top_logprobs", [{}])[0]
        top_logprobs = {str(k): float(v) for k, v in raw_top_logprobs.items()}
        p_unsafe, p_safe_sum, p_unsafe_sum = compute_unsafe_probability(top_logprobs)

        return {
            "p_unsafe": float(p_unsafe),
            "p_safe_sum": float(p_safe_sum),
            "p_unsafe_sum": float(p_unsafe_sum),
            "top_logprobs": top_logprobs,
            "latency_ms": float(latency_ms),
            "prefix_cached": self.cache is not None
        }
