#!/usr/bin/env python3
"""
Run all test modules individually to avoid cross-contamination.

This script runs each test module separately and provides a summary of results.
Running tests individually avoids database patching conflicts between modules.
"""

import subprocess
import sys
from pathlib import Path

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

# Test modules to run
TEST_MODULES = [
    "tests/test_web_interface.py",
    "tests/test_settings_service.py",
    "tests/test_priority_rules.py",
    "tests/test_ai/test_priority_integration.py",
    "tests/test_chain_stripper.py",
    "tests/test_email_processing.py",
]


def run_test_module(module_path):
    """Run a single pytest module and return results."""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}Running: {module_path}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", module_path, "-v", "--tb=short", "-q"],
        capture_output=False,
        text=True
    )

    return result.returncode == 0


def run_behave():
    """Run the Behave BDD test suite and return pass/fail."""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}Running: features/ (Behave BDD){RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    behave_exe = Path("venv/Scripts/behave.exe")
    result = subprocess.run(
        [str(behave_exe), "features/", "--no-capture"],
        capture_output=False,
        text=True
    )

    return result.returncode == 0


def main():
    """Run all test modules and report results."""
    print(f"\n{BOLD}{BLUE}EmailTools Test Suite Runner{RESET}")
    print(f"{BLUE}Running each module individually to avoid cross-contamination{RESET}\n")

    results = {}

    for module in TEST_MODULES:
        success = run_test_module(module)
        results[module] = success

    # Run Behave BDD suite
    bdd_success = run_behave()
    results["features/ (BDD)"] = bdd_success

    # Print summary
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


if __name__ == "__main__":
    sys.exit(main())
