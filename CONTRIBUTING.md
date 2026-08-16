# Contributing to Antigravity Auto Mode

Thank you for your interest in contributing to **Antigravity Auto Mode** (`antigravity-auto-mode`)! We welcome bug fixes, documentation improvements, safety eval dataset contributions, and performance enhancements.

---

## 🛠️ Development Setup

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/av-elier/antigravity-auto-mode.git
cd antigravity-auto-mode

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
```

---

## 🔒 Master Code Invariants

All pull requests must strictly preserve the following architectural guarantees:

1. **Zero Client Dependencies:** `client/` and `scripts/eval_guard.py` must NEVER import non-standard-library packages.
2. **Universal Exit Code 0:** All hook exit paths must return status code `0` to comply with Antigravity 2.0 JSON contract handling.
3. **Fail-Closed Fallback:** When the inference daemon is offline or encounters errors, always default to `{"decision": "force_ask", ...}`.
4. **Single-Token Classification:** Real-time production inference must remain constrained to `max_tokens=1` logit normalization.
5. **Zero False Allows ($FN = 0$):** Safety dataset evaluation must not introduce false allows on destructive actions.

---

## 🧪 Testing & Verification

Before opening a pull request, run the full test suite and verify that all suites pass:

```bash
# Run all tests (< 10 seconds)
python scripts/run_tests.py --kind all

# Run specific suite
python scripts/run_tests.py --kind unit
python scripts/run_tests.py --kind integration
python scripts/run_tests.py --kind e2e
python scripts/run_tests.py --kind evals

# Run via pytest
pytest -v
```

---

## 📝 Pull Request Guidelines

1. **Keep PRs focused:** One feature or bugfix per PR.
2. **Include tests:** Any new logic or bug fix must include a corresponding test under `tests/unit/`, `tests/integration/`, or `tests/e2e/`.
3. **Update documentation:** If altering CLI flags, configuration schema, or sidecar behavior, update `README.md` and relevant `AGENT.md` files.
4. **Follow commit conventions:** Use conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `perf:`).
