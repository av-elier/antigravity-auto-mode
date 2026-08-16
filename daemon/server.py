"""HTTP Daemon Server for Shieldstral Guardrail."""
import argparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import threading
import time
from typing import Optional, Any
from pathlib import Path

from .engine import ShieldstralEngine
from .mock_engine import MockShieldstralEngine
from policy.prompt_template import build_shieldstral_prompt
from policy.safety_policy import SafetyPolicy, get_default_policy

# Global metrics tracking
METRICS = {
    "requests_total": 0,
    "safe_count": 0,
    "unsafe_count": 0,
    "total_latency_ms": 0.0,
}
METRICS_LOCK = threading.Lock()


class GuardRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request handler for Shieldstral evaluation requests."""

    def _send_json(self, status_code: int, data: dict):
        response = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self):
        if self.path == "/health":
            engine_name = "mock" if getattr(self.server, "is_mock", False) else "llama_cpp"
            model_path = getattr(self.server, "model_path", "mock")
            prefix_cached = getattr(self.server.engine, "prefix_cached", False)
            self._send_json(200, {
                "status": "healthy",
                "engine": engine_name,
                "model": model_path,
                "prefix_cache": prefix_cached
            })
        elif self.path == "/policy":
            policy = getattr(self.server, "policy", get_default_policy())
            self._send_json(200, {
                "policy": policy.to_prompt_text()
            })
        elif self.path == "/metrics":
            with METRICS_LOCK:
                avg_latency = (
                    METRICS["total_latency_ms"] / METRICS["requests_total"]
                    if METRICS["requests_total"] > 0 else 0.0
                )
                data = {
                    "requests_total": METRICS["requests_total"],
                    "safe_count": METRICS["safe_count"],
                    "unsafe_count": METRICS["unsafe_count"],
                    "avg_latency_ms": round(avg_latency, 2)
                }
            self._send_json(200, data)
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        if self.path == "/shutdown":
            self._send_json(200, {"message": "Server shutting down..."})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        if self.path != "/evaluate":
            self._send_json(404, {"error": "Endpoint not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            self._send_json(400, {"error": "Missing request body"})
            return

        try:
            body = self.rfile.read(content_length).decode("utf-8")
            req = json.loads(body)

            # Build prompt if tool & args provided, or use direct prompt
            prompt = req.get("prompt")
            tool = req.get("tool", "")
            args = req.get("args", {})
            policy = getattr(self.server, "policy", get_default_policy())

            engine = self.server.engine

            # Support prefix caching: thread-safe forward pass with engine inference lock
            with self.server.inference_lock:
                if prompt:
                    result = engine.evaluate(prompt)
                elif hasattr(engine, "evaluate_tool"):
                    result = engine.evaluate_tool(tool, args, policy)
                else:
                    full_prompt = build_shieldstral_prompt(tool, args, policy)
                    result = engine.evaluate(full_prompt)

            p_unsafe = result["p_unsafe"]
            latency_ms = result.get("latency_ms", 0.0)

            # Update metrics
            with METRICS_LOCK:
                METRICS["requests_total"] += 1
                METRICS["total_latency_ms"] += latency_ms
                if p_unsafe < 0.20:
                    METRICS["safe_count"] += 1
                else:
                    METRICS["unsafe_count"] += 1

            self._send_json(200, {
                "p_unsafe": p_unsafe,
                "is_safe": p_unsafe < 0.20,
                "latency_ms": round(latency_ms, 2),
                "top_logprobs": result.get("top_logprobs", {})
            })

        except Exception as e:
            self._send_json(500, {"error": str(e), "p_unsafe": 1.0})

    def log_message(self, format, *args):
        # Suppress standard access logging to minimize I/O latency
        if getattr(self.server, "verbose", False):
            super().log_message(format, *args)


def write_endpoint_file(host: str, port: int, pid: Optional[int] = None, data_dir: Optional[str] = None) -> list:
    """Writes active daemon endpoint JSON to known discovery paths."""
    if pid is None:
        pid = os.getpid()

    endpoint_data = {
        "host": host,
        "port": port,
        "url": f"http://{host}:{port}",
        "pid": pid,
        "started_at": time.time()
    }

    written_paths = []
    discovery_dirs = []

    if data_dir:
        discovery_dirs.append(Path(data_dir))
    elif "ANTIGRAVITY_EXECUTABLE_DATA_DIR" in os.environ:
        discovery_dirs.append(Path(os.environ["ANTIGRAVITY_EXECUTABLE_DATA_DIR"]))

    # Standard sidecar data dirs
    discovery_dirs.append(Path.home() / ".gemini" / "antigravity" / "sidecar_data" / "antigravity-auto-mode" / "shieldstral-daemon")
    discovery_dirs.append(Path.home() / ".gemini" / "antigravity" / "sidecar_data" / "agy-shieldstral-guard" / "shieldstral-daemon")

    # Project cache dir
    project_cache = Path(__file__).resolve().parent.parent / ".cache"
    discovery_dirs.append(project_cache)

    # User home cache
    discovery_dirs.append(Path.home() / ".cache")

    for d in discovery_dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
            fname = "endpoint.json" if d != Path.home() / ".cache" else "agy_shieldstral_guard_endpoint.json"
            target_file = d / fname
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(endpoint_data, f, indent=2)
            written_paths.append(target_file)
        except Exception:
            pass

    return written_paths


def remove_endpoint_file(written_paths: Optional[list] = None, data_dir: Optional[str] = None):
    """Cleans up endpoint files on daemon shutdown."""
    if written_paths:
        for p in written_paths:
            try:
                path_obj = Path(p)
                if path_obj.exists():
                    path_obj.unlink()
            except Exception:
                pass
        return

    check_dirs = []
    if data_dir:
        check_dirs.append(Path(data_dir))
    if "ANTIGRAVITY_EXECUTABLE_DATA_DIR" in os.environ:
        check_dirs.append(Path(os.environ["ANTIGRAVITY_EXECUTABLE_DATA_DIR"]))
    check_dirs.append(Path.home() / ".gemini" / "antigravity" / "sidecar_data" / "antigravity-auto-mode" / "shieldstral-daemon")
    check_dirs.append(Path.home() / ".gemini" / "antigravity" / "sidecar_data" / "agy-shieldstral-guard" / "shieldstral-daemon")
    check_dirs.append(Path(__file__).resolve().parent.parent / ".cache")
    check_dirs.append(Path.home() / ".cache")

    for d in check_dirs:
        try:
            fname = "endpoint.json" if d != Path.home() / ".cache" else "agy_shieldstral_guard_endpoint.json"
            target_file = d / fname
            if target_file.exists():
                target_file.unlink()
        except Exception:
            pass


class GuardHTTPServer(ThreadingHTTPServer):
    """Custom ThreadingHTTPServer tracking actual port and managing endpoint file lifecycle."""

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True, data_dir=None):
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        self.actual_host, self.actual_port = self.server_address
        self.data_dir = data_dir
        self.endpoint_files = write_endpoint_file(self.actual_host, self.actual_port, data_dir=self.data_dir)

    def server_close(self):
        remove_endpoint_file(getattr(self, "endpoint_files", None), data_dir=getattr(self, "data_dir", None))
        super().server_close()


def create_server(
    host: str = "127.0.0.1",
    port: int = 0,
    model_path: Optional[str] = None,
    mock: bool = False,
    gpu_layers: int = 99,
    ctx_size: int = 2048,
    enable_prefix_cache: bool = True,
    prefix_cache_mb: int = 512,
    verbose: bool = False,
    policy_path: Optional[str] = None,
    data_dir: Optional[str] = None
) -> GuardHTTPServer:
    """Instantiates and configures the concurrent HTTP daemon server (port 0 = dynamic ephemeral port)."""
    if mock or not model_path or not Path(model_path).exists():
        if not mock and model_path and not Path(model_path).exists():
            print(f"[Warning] Model '{model_path}' not found. Falling back to Mock engine.")
        engine = MockShieldstralEngine(verbose=verbose)
        is_mock = True
    else:
        print(f"[Info] Loading Shieldstral weights from {model_path} (gpu_layers={gpu_layers}, prefix_cache={enable_prefix_cache})...")
        engine = ShieldstralEngine(
            model_path=model_path,
            n_ctx=ctx_size,
            n_gpu_layers=gpu_layers,
            enable_prefix_cache=enable_prefix_cache,
            prefix_cache_mb=prefix_cache_mb,
            verbose=verbose
        )
        is_mock = False

    server = GuardHTTPServer((host, port), GuardRequestHandler, data_dir=data_dir)
    server.engine = engine
    server.is_mock = is_mock
    server.model_path = model_path or "mock"
    server.verbose = verbose
    server.inference_lock = threading.Lock()
    server.policy = (
        SafetyPolicy.from_file(policy_path)
        if policy_path
        else get_default_policy()
    )

    # Warmup KV cache with static policy prefix on startup
    if verbose:
        print("[Info] Warming up prompt prefix cache...")
    engine.warmup(server.policy)

    return server


def run_server(
    host: str = "127.0.0.1",
    port: int = 0,
    model_path: Optional[str] = None,
    mock: bool = False,
    gpu_layers: int = 99,
    ctx_size: int = 2048,
    enable_prefix_cache: bool = True,
    prefix_cache_mb: int = 512,
    verbose: bool = False,
    policy_path: Optional[str] = None,
    data_dir: Optional[str] = None
):
    """Runs the server in the foreground until interrupted."""
    server = create_server(
        host=host,
        port=port,
        model_path=model_path,
        mock=mock,
        gpu_layers=gpu_layers,
        ctx_size=ctx_size,
        enable_prefix_cache=enable_prefix_cache,
        prefix_cache_mb=prefix_cache_mb,
        verbose=verbose,
        policy_path=policy_path,
        data_dir=data_dir
    )
    actual_port = server.actual_port
    print(f"[Shieldstral Guardrail] Server listening on http://{host}:{actual_port} (Mock={server.is_mock}, PrefixCache={enable_prefix_cache}, Port={'dynamic' if port == 0 else actual_port})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Shieldstral Guardrail] Shutting down...")
    finally:
        server.server_close()


def start_daemon_background(
    host: str = "127.0.0.1",
    port: int = 0,
    model_path: Optional[str] = None,
    mock: bool = False,
    gpu_layers: int = 99,
    ctx_size: int = 2048,
    enable_prefix_cache: bool = True,
    prefix_cache_mb: int = 512,
    data_dir: Optional[str] = None
) -> threading.Thread:
    """Helper to start the daemon in a background thread for tests."""
    server = create_server(
        host=host,
        port=port,
        model_path=model_path,
        mock=mock,
        gpu_layers=gpu_layers,
        ctx_size=ctx_size,
        enable_prefix_cache=enable_prefix_cache,
        prefix_cache_mb=prefix_cache_mb,
        data_dir=data_dir
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.server = server
    thread.start()
    return thread


def stop_daemon(server: ThreadingHTTPServer):
    """Stops the daemon server."""
    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shieldstral Local Guardrail Daemon")
    parser.add_argument("--model", type=str, default="./models/Shieldstral-1.0-3B-Q4_K_M.gguf", help="Path to GGUF model")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface")
    parser.add_argument("--port", type=int, default=0, help="Port to listen on (0 for dynamic ephemeral port)")
    parser.add_argument("--mock", action="store_true", help="Force mock engine mode")
    parser.add_argument("--ctx", type=int, default=2048, help="Context window size")
    parser.add_argument("--gpu-layers", type=int, default=99, help="Number of GPU layers to offload")
    parser.add_argument("--no-prefix-cache", action="store_true", help="Disable LLM prefix cache")
    parser.add_argument("--prefix-cache-mb", type=int, default=512, help="Prefix cache RAM capacity in MB")
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
        enable_prefix_cache=not args.no_prefix_cache,
        prefix_cache_mb=args.prefix_cache_mb,
        verbose=args.verbose,
        policy_path=args.policy
    )
