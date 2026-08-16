"""Installation and registration script for Antigravity Shieldstral Plugin."""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def enable_sidecar_in_config(config_dir: Path, sidecar_id: str = "antigravity-auto-mode/shieldstral-daemon") -> bool:
    """Enables the sidecar in config.json."""
    config_file = config_dir / "config.json"
    config_data = {}
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception:
            config_data = {}

    if "sidecars" not in config_data:
        config_data["sidecars"] = {}

    config_data["sidecars"][sidecar_id] = {
        "enabled": True
    }

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        print(f"[Install] Warning: Could not update config.json: {e}", file=sys.stderr)
        return False


def install_plugin(global_install: bool = True, target_dir: str = None, enable_sidecar: bool = True):
    """Installs the plugin to global ~/.gemini/config or local workspace .agents/."""
    if target_dir:
        config_base = Path(target_dir)
        destination = config_base / "plugins" / "antigravity-auto-mode"
    elif global_install:
        config_base = Path.home() / ".gemini" / "config"
        destination = config_base / "plugins" / "antigravity-auto-mode"
    else:
        config_base = Path.cwd() / ".agents"
        destination = config_base / "plugins" / "antigravity-auto-mode"

    print(f"[Install] Installing Antigravity Auto Mode Plugin to: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    # Files to copy/link
    items_to_copy = [
        "plugin.json",
        "hooks.json",
        "scripts",
        "client",
        "policy",
        "daemon",
        "sidecars",
        "cli",
        "config"
    ]

    for item in items_to_copy:
        src = PROJECT_ROOT / item
        if not src.exists():
            continue
        dst = destination / item
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, dst)

    sidecar_configured = False
    if enable_sidecar:
        sidecar_configured = enable_sidecar_in_config(config_base)

    print("\n[Success] Antigravity Auto Mode Plugin installed successfully!")
    print(f"Location: {destination}")
    if sidecar_configured:
        print(f"Sidecar Registered: 'antigravity-auto-mode/shieldstral-daemon' (Enabled in {config_base / 'config.json'})")
        print("Antigravity will automatically launch and manage the Shieldstral inference daemon!")
    print("\nNext Steps:")
    print("1. Launch Antigravity CLI:")
    print("   agy")
    print("2. (Optional) Inspect daemon status or run standalone tests anytime:")
    print("   python -m cli.guardctl status\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install Antigravity Auto Mode Plugin")
    parser.add_argument("--local", action="store_true", help="Install to local workspace (.agents/) instead of global (~/.gemini/config)")
    parser.add_argument("--target", type=str, help="Custom target directory")
    parser.add_argument("--no-enable-sidecar", action="store_true", help="Do not automatically enable sidecar in config.json")
    args = parser.parse_args()

    install_plugin(
        global_install=not args.local,
        target_dir=args.target,
        enable_sidecar=not args.no_enable_sidecar
    )
