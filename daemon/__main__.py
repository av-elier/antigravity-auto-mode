"""Entrypoint for running daemon directly via python -m daemon."""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from daemon.server import run_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shieldstral Local Guardrail Daemon")
    parser.add_argument("--model", type=str, default="./models/Shieldstral-1.0-3B-Q4_K_M.gguf", help="Path to GGUF model")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--mock", action="store_true", help="Force mock engine mode")
    parser.add_argument("--ctx", type=int, default=2048, help="Context window size")
    parser.add_argument("--gpu-layers", type=int, default=99, help="Number of GPU layers to offload")
    parser.add_argument("--policy", type=str, default=None, help="Custom policy file path")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        model_path=args.model,
        mock=args.mock,
        gpu_layers=args.gpu_layers,
        ctx_size=args.ctx,
        verbose=args.verbose,
        policy_path=args.policy
    )
