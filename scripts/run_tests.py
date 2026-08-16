"""Unified Test Runner CLI for Shieldstral Antigravity Guardrail.

Executes and benchmarks categorized test suites (unit, integration, e2e, evals, cache, sidecar).
Supports pytest with automatic fallback to standard library unittest.
"""
import argparse
import os
import sys
import time
import unittest
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mapping test categories to directories and markers
KIND_MAPPING = {
    "unit": {
        "dir": "tests/unit",
        "marker": "unit",
        "description": "In-memory unit tests (math, policies, cache hashing, plugin schemas)",
        "budget_sec": 1.0
    },
    "integration": {
        "dir": "tests/integration",
        "marker": "integration and not real_model",
        "description": "Integration tests (server API, hook client, sidecar lifecycle, cache timing)",
        "budget_sec": 8.0
    },
    "e2e": {
        "dir": "tests/e2e",
        "marker": "e2e",
        "description": "End-to-end simulation tests (subprocess stdin/stdout piping, guardctl CLI)",
        "budget_sec": 5.0
    },
    "evals": {
        "dir": "tests/eval_suite",
        "marker": "evals and not real_model",
        "description": "Safety evaluation dataset benchmarks and prompt regression tests",
        "budget_sec": 1.0
    },
    "cache": {
        "dir": "tests",
        "marker": "cache and not real_model",
        "description": "Quantitative KV prefix cache and SHA-256 client cache performance",
        "budget_sec": 3.0
    },
    "sidecar": {
        "dir": "tests",
        "marker": "sidecar",
        "description": "Antigravity sidecar configuration, schema, dynamic port 0 discovery",
        "budget_sec": 5.0
    },
    "real-model": {
        "dir": "tests",
        "marker": "real_model",
        "description": "Live Shieldstral 3B GGUF weights inference & KV cache verification",
        "budget_sec": 60.0
    }
}


def has_pytest() -> bool:
    """Checks if pytest is installed in current Python environment."""
    try:
        import pytest
        return True
    except ImportError:
        return False


def run_with_pytest(kind: str, verbose: bool = False, fail_fast: bool = False, filter_expr: Optional[str] = None) -> Dict[str, Any]:
    """Runs tests using pytest runner."""
    import pytest

    if kind == "real-model":
        os.environ["RUN_REAL_MODEL"] = "1"
    else:
        os.environ["RUN_REAL_MODEL"] = "0"

    args = ["-c", str(PROJECT_ROOT / "pyproject.toml")]
    if verbose:
        args.append("-v")
    if fail_fast:
        args.append("-x")
    if filter_expr:
        args.extend(["-k", filter_expr])

    if kind == "all":
        # All tests except real_model by default unless specified
        args.extend(["-m", "not real_model"])
    elif kind == "fast" or kind == "smoke":
        # Fast smoke test: unit + mock evals
        args.extend(["-m", "(unit or evals) and not real_model and not slow"])
    elif kind in KIND_MAPPING:
        cfg = KIND_MAPPING[kind]
        target_dir = cfg["dir"]
        args.extend([target_dir, "-m", cfg["marker"]])

    print(f"\n[Test Runner] Executing pytest: {' '.join(args)}")
    t0 = time.perf_counter()
    exit_code = pytest.main(args)
    duration = time.perf_counter() - t0

    return {
        "runner": "pytest",
        "kind": kind,
        "exit_code": int(exit_code),
        "passed": exit_code == 0,
        "duration_sec": round(duration, 3)
    }


def run_with_unittest(kind: str, verbose: bool = False, fail_fast: bool = False) -> Dict[str, Any]:
    """Fallback runner using standard library unittest."""
    if kind == "real-model":
        os.environ["RUN_REAL_MODEL"] = "1"
    else:
        os.environ["RUN_REAL_MODEL"] = "0"

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if kind == "all" or kind == "fast" or kind == "smoke":
        suite = loader.discover(start_dir=str(PROJECT_ROOT / "tests"), pattern="test_*.py")
    elif kind in KIND_MAPPING:
        suite = loader.discover(start_dir=str(PROJECT_ROOT / KIND_MAPPING[kind]["dir"]), pattern="test_*.py")
    else:
        suite = loader.discover(start_dir=str(PROJECT_ROOT / "tests"), pattern="test_*.py")

    verbosity = 2 if verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity, failfast=fail_fast)

    print(f"\n[Test Runner] Executing unittest suite for kind='{kind}' (count={suite.countTestCases()})...")
    t0 = time.perf_counter()
    result = runner.run(suite)
    duration = time.perf_counter() - t0

    return {
        "runner": "unittest",
        "kind": kind,
        "total": result.testsRun,
        "errors": len(result.errors),
        "failures": len(result.failures),
        "skipped": len(result.skipped),
        "passed": result.wasSuccessful(),
        "exit_code": 0 if result.wasSuccessful() else 1,
        "duration_sec": round(duration, 3)
    }


def run_test_suites(
    kind: str = "all",
    runner_choice: str = "auto",
    verbose: bool = False,
    fail_fast: bool = False,
    filter_expr: Optional[str] = None
) -> int:
    """Orchestrates test execution across kinds with execution speed analysis."""
    use_pytest = False
    if runner_choice == "pytest":
        if not has_pytest():
            print("[Test Runner] Error: pytest is requested but not installed.")
            return 1
        use_pytest = True
    elif runner_choice == "unittest":
        use_pytest = False
    else:  # auto
        use_pytest = has_pytest()

    print("=" * 80)
    print(" Shieldstral Guardrail CI & DevEx Test Runner")
    print("=" * 80)
    print(f"Target Kind:  {kind.upper()}")
    print(f"Runner:       {'pytest (Native)' if use_pytest else 'unittest (Standard Library Fallback)'}")
    print(f"Working Dir:  {PROJECT_ROOT}")
    print("=" * 80)

    results = []

    # If running 'all', run through categorized suites for speed analysis
    if kind == "all":
        categories = ["unit", "integration", "e2e", "evals"]
        overall_success = True

        for cat in categories:
            print(f"\n---> Running Suite: {cat.upper()} ({KIND_MAPPING[cat]['description']})")
            if use_pytest:
                res = run_with_pytest(cat, verbose=verbose, fail_fast=fail_fast, filter_expr=filter_expr)
            else:
                res = run_with_unittest(cat, verbose=verbose, fail_fast=fail_fast)
            results.append(res)
            if not res["passed"]:
                overall_success = False
                if fail_fast:
                    break

        print_execution_summary(results)
        return 0 if overall_success else 1
    else:
        if use_pytest:
            res = run_with_pytest(kind, verbose=verbose, fail_fast=fail_fast, filter_expr=filter_expr)
        else:
            res = run_with_unittest(kind, verbose=verbose, fail_fast=fail_fast)

        results.append(res)
        print_execution_summary(results)
        return res["exit_code"]


def print_execution_summary(results: List[Dict[str, Any]]):
    """Prints a structured summary table and execution speed analysis."""
    print("\n" + "=" * 80)
    print(" Test Suite Execution Summary & Performance Breakdown")
    print("=" * 80)
    print(f"{'Suite / Kind':<16} {'Status':<10} {'Duration':<12} {'Budget':<10} {'Perf Rating':<15}")
    print("-" * 80)

    total_time = 0.0
    all_passed = True

    for r in results:
        kind = r["kind"]
        passed = r["passed"]
        duration = r["duration_sec"]
        total_time += duration
        if not passed:
            all_passed = False

        status_str = "[PASSED]" if passed else "[FAILED]"
        budget_sec = KIND_MAPPING.get(kind, {}).get("budget_sec", 10.0)
        budget_str = f"<= {budget_sec:.1f}s"

        if duration <= budget_sec * 0.5:
            perf_rating = "EXCELLENT (Fast)"
        elif duration <= budget_sec:
            perf_rating = "OPTIMAL (Within Budget)"
        else:
            perf_rating = "SLOW (Exceeded Budget)"

        print(f"{kind.upper():<16} {status_str:<10} {duration:6.2f}s     {budget_str:<10} {perf_rating:<15}")

    print("-" * 80)
    print(f"Total Execution Time: {total_time:.2f} seconds")
    print(f"Overall Test Result:  {'ALL SUITES PASSED' if all_passed else 'SOME SUITES FAILED'}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Shieldstral Guardrail Unified Test Runner")
    parser.add_argument(
        "--kind",
        type=str,
        default="all",
        choices=["all", "unit", "integration", "e2e", "evals", "cache", "sidecar", "fast", "smoke", "real-model"],
        help="Category of tests to run (default: all)"
    )
    parser.add_argument(
        "--runner",
        type=str,
        default="auto",
        choices=["auto", "pytest", "unittest"],
        help="Test runner backend (default: auto)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose test reporting")
    parser.add_argument("-x", "--fail-fast", action="store_true", help="Exit immediately on first test failure")
    parser.add_argument("-k", "--filter", type=str, default=None, help="Filter test names by keyword expression")
    args = parser.parse_args()

    sys.exit(run_test_suites(
        kind=args.kind,
        runner_choice=args.runner,
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        filter_expr=args.filter
    ))


if __name__ == "__main__":
    main()
