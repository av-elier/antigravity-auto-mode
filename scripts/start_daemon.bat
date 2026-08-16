@echo off
REM Shieldstral Local Guardrail Daemon Launcher (Windows)
echo Starting Shieldstral Guardrail Daemon...
python -m daemon --host 127.0.0.1 --port 8080 %*
