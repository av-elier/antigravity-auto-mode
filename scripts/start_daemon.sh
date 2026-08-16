#!/usr/bin/env bash
# Shieldstral Local Guardrail Daemon Launcher (Linux / macOS)
set -e
echo "Starting Shieldstral Guardrail Daemon..."
exec python3 -m daemon --host 127.0.0.1 --port 8080 "$@"
