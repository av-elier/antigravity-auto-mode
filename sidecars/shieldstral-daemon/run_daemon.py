#!/usr/bin/env python3
"""
Antigravity Sidecar Launcher for Shieldstral Guardrail Daemon.

This script is executed by the Antigravity runtime when managing the
'antigravity-auto-mode/shieldstral-daemon' sidecar.
"""
import argparse
import os
import signal
import sys
from pathlib import Path

# Resolve plugin root: sidecars/shieldstral-daemon/ -> plugin root
SIDECAR_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SIDECAR_DIR.parent.parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from client.eval_client import load_config
from daemon.server import run_server


def setup_signal_handlers():
    """Register graceful shutdown handlers for sidecar process lifecycle."""
    def _sig_handler(signum, frame):
        print(f"[Sidecar] Received signal {signum}, initiating graceful shutdown...", file=sys.stderr)
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    except (AttributeError, ValueError):
        pass


def main():
    setup_signal_handlers()

    parser = argparse.ArgumentParser(description="Shieldstral Guardrail Sidecar Daemon")
    parser.add_argument("--host", type=str, default=None, help="Host interface")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on")
    parser.add_argument("--model", type=str, default=None, help="Path to GGUF model")
    parser.add_argument("--mock", action="store_true", help="Force mock engine mode")
    parser.add_argument("--gpu-layers", type=int, default=None, help="GPU layers to offload")
    parser.add_argument("--ctx", type=int, default=None, help="Context size")
    parser.add_argument("--auto-download", action="store_true", default=True, help="Auto download weights if missing")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    config = load_config()
    daemon_cfg = config.get("daemon", {})

    host = args.host or os.environ.get("AGY_GUARD_HOST") or daemon_cfg.get("host", "127.0.0.1")
    
    port_env = os.environ.get("AGY_GUARD_PORT")
    port = args.port if args.port is not None else (int(port_env) if port_env else daemon_cfg.get("port", 0))

    gpu_layers = args.gpu_layers or daemon_cfg.get("gpu_layers", 99)
    ctx = args.ctx or daemon_cfg.get("ctx_size", 2048)

    # Check for ANTIGRAVITY_EXECUTABLE_DATA_DIR (set by Antigravity runtime for sidecars)
    data_dir = os.environ.get("ANTIGRAVITY_EXECUTABLE_DATA_DIR")
    if data_dir:
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        print(f"[Sidecar] Runtime data directory active: {data_dir}")

    # Resolve model path
    raw_model_path = args.model or daemon_cfg.get("model_path", "./models/Shieldstral-1.0-3B-Q4_K_M.gguf")
    model_path_obj = Path(raw_model_path)
    if not model_path_obj.is_absolute():
        # Check relative to plugin root
        plugin_model_path = PLUGIN_ROOT / raw_model_path
        if plugin_model_path.exists():
            model_path_obj = plugin_model_path
        elif data_dir and (Path(data_dir) / "models" / model_path_obj.name).exists():
            model_path_obj = Path(data_dir) / "models" / model_path_obj.name
        else:
            model_path_obj = plugin_model_path

    model = str(model_path_obj)

    # Auto-download model if missing and not in mock mode
    if not args.mock and not model_path_obj.exists():
        if args.auto_download:
            print(f"[Sidecar] Model weights not found at {model}. Initiating auto-download...")
            try:
                from scripts.download_model import download_hf_model
                target_dest = (Path(data_dir) / "models" / "Shieldstral-1.0-3B-Q4_K_M.gguf") if data_dir else model_path_obj
                downloaded = download_hf_model(dest_path=target_dest)
                model = str(downloaded)
            except Exception as e:
                print(f"[Sidecar] Warning: Model download failed ({e}). Falling back to mock engine.", file=sys.stderr)
                args.mock = True
        else:
            print(f"[Sidecar] Model not found at {model} and auto-download disabled. Using mock engine.", file=sys.stderr)
            args.mock = True

    print(f"[Sidecar] Launching Shieldstral daemon (host={host}, requested_port={port}, engine={'mock' if args.mock else 'llama_cpp'})")
    run_server(
        host=host,
        port=port,
        model_path=model,
        mock=args.mock,
        gpu_layers=gpu_layers,
        ctx_size=ctx,
        verbose=args.verbose,
        data_dir=data_dir
    )


if __name__ == "__main__":
    main()
