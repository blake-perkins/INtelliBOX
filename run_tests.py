#!/usr/bin/env python3
"""
Run test modules individually to avoid cross-contamination.

Usage:
  python run_tests.py           # Fast tests only (~15s)
  python run_tests.py --slow    # Fast + slow + BDD (~1-2min)
  python run_tests.py --full    # Everything incl. E2E (~4-5min)
  python run_tests.py --e2e     # Fast + E2E (~75s)
  python run_tests.py --help    # Show this help
"""

import os
import subprocess
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Color codes for terminal output (disabled on Windows for simplicity)
if sys.platform == 'win32':
    GREEN = RED = YELLOW = BLUE = BOLD = RESET = ''
else:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# ── Test tiers ──────────────────────────────────────────────────────────────

# Tier 1: Fast unit/integration tests (~15s)
FAST_MODULES = [
    "tests/test_datetime_utils.py",
    "tests/test_chain_stripper.py",
    "tests/test_logging_rotation.py",
    "tests/test_priority_rules.py",
    "tests/test_settings_service.py",
    "tests/test_database_maintenance.py",
    "tests/test_file_watcher.py",
    "tests/test_ai/test_priority_integration.py",
    "tests/test_ai_client.py",
    "tests/test_email_processing.py",
    "tests/test_knowledge_base.py",
]

# Tier 2: Slower integration tests (web routes, auth with bcrypt)
SLOW_MODULES = [
    "tests/test_web_interface.py",
    "tests/test_audit.py",
    "tests/test_auth.py",
    "tests/test_oidc.py",
]

# Per-module environment overrides (conftest.py loads before test modules,
# so env vars must be set in the subprocess env, not just os.environ).
_MODULE_ENV = {
    "tests/test_auth.py": {"AUTH_MODE": "local"},
    "tests/test_oidc.py": {
        "AUTH_MODE": "oidc",
        "OIDC_ISSUER_URL": "https://idp.example.com/realms/test",
        "OIDC_CLIENT_ID": "intellibox-test",
        "OIDC_CLIENT_SECRET": "test-client-secret",
    },
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _test_env(module_path):
    """Build environment for test subprocesses."""
    env = os.environ.copy()
    overrides = _MODULE_ENV.get(module_path, {})
    env["AUTH_MODE"] = overrides.get("AUTH_MODE", "disabled")
    env.update(overrides)
    return env


def run_test_module(module_path):
    """Run a single pytest module and return results."""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}Running: {module_path}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", module_path, "-v", "--tb=short", "-q"],
        capture_output=False,
        text=True,
        env=_test_env(module_path),
    )

    return result.returncode == 0


def run_behave(tags=None):
    """Run the Behave BDD test suite and return pass/fail."""
    label = "features/ (BDD)"
    if tags:
        label += f" [{tags}]"

    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}Running: {label}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    # Use python -m behave for reliable exit codes on all platforms
    if sys.platform == 'win32':
        cmd = [sys.executable, "-m", "behave", "features/", "--no-capture"]
    else:
        import shutil
        behave_cmd = shutil.which("behave") or "behave"
        cmd = [behave_cmd, "features/", "--no-capture"]

    if tags:
        cmd.extend(["--tags", tags])

    result = subprocess.run(
        cmd,
        capture_output=False,
        text=True,
        env=_test_env("behave"),
    )

    return result.returncode == 0


def print_summary(results):
    """Print the test summary and return exit code."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    passed = sum(1 for success in results.values() if success)
    total = len(results)

    for module, success in results.items():
        status = f"{GREEN}✓ PASS{RESET}" if success else f"{RED}✗ FAIL{RESET}"
        print(f"  {status}  {module}")

    print(f"\n{BLUE}{'=' * 70}{RESET}")

    if passed == total:
        print(f"{GREEN}{BOLD}All {total} test modules passed!{RESET} ✨")
        return 0
    else:
        print(f"{YELLOW}{BOLD}{passed}/{total} test modules passed{RESET}")
        print(f"{RED}Run failed modules individually for details:{RESET}")
        for module, success in results.items():
            if not success:
                if "BDD" in module:
                    print(f"  {RED}./venv/Scripts/behave.exe features/ --no-capture{RESET}")
                else:
                    print(f"  {RED}./venv/Scripts/python.exe -m pytest {module} -v{RESET}")
        return 1


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    """Run test modules based on the selected tier."""
    flags = set(sys.argv[1:])
    valid = {"--fast", "--slow", "--full", "--e2e", "--help"}
    unknown = flags - valid

    if unknown or "--help" in flags:
        print(f"\n{BOLD}INtelliBOX Test Suite Runner{RESET}\n")
        print("Usage: python run_tests.py [--slow | --full | --e2e | --help]\n")
        print(f"  {BOLD}(no flags){RESET}   Fast tests only (~15s)")
        print(f"  {BOLD}--slow{RESET}       Fast + slow tests + BDD (~1-2min)")
        print(f"  {BOLD}--full{RESET}       Everything including E2E (~4-5min)")
        print(f"  {BOLD}--e2e{RESET}        Fast + E2E browser tests (~75s)")
        print(f"  {BOLD}--help{RESET}       Show this help")
        return 1 if unknown else 0

    include_slow = "--slow" in flags or "--full" in flags
    include_bdd = "--slow" in flags or "--full" in flags
    include_e2e = "--e2e" in flags or "--full" in flags

    tier = "full" if "--full" in flags else "slow" if "--slow" in flags else "e2e" if "--e2e" in flags else "fast"
    print(f"\n{BOLD}{BLUE}INtelliBOX Test Suite Runner{RESET} [{tier}]")
    print(f"{BLUE}Running each module individually to avoid cross-contamination{RESET}\n")

    results = {}

    # Tier 1: Always run fast modules
    for module in FAST_MODULES:
        results[module] = run_test_module(module)

    # Tier 2: Slow modules (--slow or --full)
    if include_slow:
        for module in SLOW_MODULES:
            results[module] = run_test_module(module)

    # BDD (--slow or --full)
    if include_bdd:
        results["features/ (BDD)"] = run_behave()

    # E2E (--e2e or --full)
    if include_e2e:
        results["tests/e2e/ (E2E)"] = run_test_module("tests/e2e/")

    return print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
