# Installation & Setup Guide

This guide walks you through setting up the **Antigravity Auto Mode** plugin on your local machine.

---

## 💻 System Requirements

* **Operating System:** Linux, macOS, or Windows 10/11
* **Python:** Python 3.8 or higher
* **Memory & Hardware:**
  * **GPU (Recommended):** NVIDIA GPU with $\ge 3\text{ GB}$ VRAM (CUDA), Apple Silicon (Metal), or Vulkan.
  * **CPU:** 8 GB RAM (CPU offloading supported).
* **Disk Space:** $\approx 2.5\text{ GB}$ for quantized model weights.

---

## 📦 Step-by-Step Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/av-elier/antigravity-auto-mode.git
cd antigravity-auto-mode
```

### Step 2: Install Python Dependencies

Create a virtual environment (recommended) and install requirements:

```bash
# Create virtual environment
python -m venv .venv

# Activate on Linux / macOS:
source .venv/bin/activate

# Activate on Windows:
.venv\Scripts\activate

# Install dependencies (for inference daemon):
pip install -r requirements.txt
```

> [!NOTE]
> For hardware acceleration on CUDA (NVIDIA):
> ```bash
> CMAKE_ARGS="-DLLAMA_CUDA=on" pip install --upgrade --force-reinstall llama-cpp-python
> ```
> For hardware acceleration on Apple Silicon (Metal):
> ```bash
> CMAKE_ARGS="-DLLAMA_METAL=on" pip install --upgrade --force-reinstall llama-cpp-python
> ```

---

### Step 3: Install Plugin & Sidecar into Antigravity

Register the plugin globally in your Antigravity configuration directory:

```bash
# Global installation (recommended - applies to all workspaces):
python scripts/install.py

# Or workspace-only installation (current repo only):
python scripts/install.py --local
```

> [!TIP]
> `install.py` registers the **Antigravity Sidecar** (`antigravity-auto-mode/shieldstral-daemon`) in `~/.gemini/config/config.json`. Antigravity will automatically start, monitor, and manage the daemon whenever you run `agy`!

---

### Step 4: (Optional) Pre-Download Shieldstral GGUF Model

The daemon automatically downloads the quantized 3B model on first launch. You can also pre-download the weights manually (~2.2 GB):

```bash
python scripts/download_model.py
```

The weights will be saved to `./models/Shieldstral-1.0-3B-Q4_K_M.gguf`.

---

### Step 5: Configure Antigravity Settings (Always Allow / Turbo Mode)

In Antigravity 2.0 settings (`Settings -> General -> Agent Settings -> Security Preset`):
1. **Security Preset:** Select **`Always Allow`** (or **`Full machine`** / **`Turbo`**).
2. **How it works:** In `Always Allow` mode, Antigravity attempts to run all tool executions automatically. The Shieldstral plugin acts as the active interceptor: safe commands execute immediately with 0 clicks, and destructive/sensitive actions trigger confirmation prompts (`force_ask`).
3. **No manual whitelists needed:** You do not need to manually configure regexes in *Terminal Commands* or *File Access Rules*—Shieldstral dynamically evaluates safety context.

---

### Step 6: Verify with Antigravity 2.0

Launch Antigravity:
```bash
agy
```

When the agent attempts to run benign commands (such as `pytest`, `npm test`, `git status`, or reading files), they will execute **automatically without manual approval prompts**.

When the agent attempts potentially destructive or sensitive operations (e.g. `rm -rf /`, viewing secrets, or force-pushing branches), Antigravity will pause and prompt you for confirmation!

---

## 🔧 Managing and Inspecting the Daemon (`guardctl`)

| Command | Action |
| :--- | :--- |
| `python -m cli.guardctl status` | Shows daemon health, sidecar activation, & live metrics |
| `python -m cli.guardctl benchmark` | Runs latency & throughput benchmark |
| `python -m cli.guardctl eval` | Runs safety benchmark evaluation on dataset |
| `python -m cli.guardctl clear-cache` | Clears SHA-256 safe cache |
| `python -m cli.guardctl test --tool run_command --args '{"CommandLine": "npm test"}'` | Tests single tool evaluation |
| `python -m cli.guardctl start --bg` | (Standalone mode) Starts daemon in background |
| `python -m cli.guardctl stop` | (Standalone mode) Stops daemon |
| `python scripts/run_tests.py --kind all` | Runs full automated CI test suite |
