#!/usr/bin/env python3
"""
Run PostgreSQL-specific test suite.

Requires a running PostgreSQL instance (see docker-compose.pg-test.yml):
    docker compose -f docker-compose.pg-test.yml up -d
    python run_pg_tests.py

For stress tests (requires stress profile):
    docker compose -f docker-compose.pg-test.yml --profile stress up -d
    python run_pg_tests.py --stress
"""

import os
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

# Core PG test modules (run on every invocation)
PG_TEST_MODULES = [
    "tests/test_pg_functional.py",
    "tests/test_pg_migrations.py",
    "tests/test_pg_pool.py",
    "tests/test_pg_maintenance.py",
    "tests/test_pg_web_routes.py",
    "tests/pg_integrity/",
    "tests/pg_contamination/",
    "tests/pg_migration/",
]

# Performance tests (run on every invocation, quick)
PG_PERF_MODULES = [
    "tests/pg_performance/",
]

# Stress/resilience/backup tests (run only with --stress flag)
PG_STRESS_MODULES = [
    "tests/pg_stress/",
    "tests/pg_resilience/",
    "tests/pg_backup/",
]


def run_test_module(module_path):
    """Run a single pytest module and return results."""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}Running: {module_path}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    # Build environment: disable auth (web route tests need this) and skip coverage
    env = os.environ.copy()
    env.setdefault("AUTH_MODE", "disabled")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", module_path, "-v", "--tb=short", "-q",
         "--no-cov", "-m", "not e2e and not smoke"],
        capture_output=False,
        text=True,
        env=env,
    )

    return result.returncode == 0


def check_pg_available():
    """Check if PostgreSQL test instance is reachable."""
    pg_url = os.environ.get(
        "PG_TEST_DATABASE_URL",
        "postgresql+psycopg://intellibox_test:test_password@localhost:5433/intellibox_test",
    )
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(pg_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception as e:
        print(f"{RED}PostgreSQL test instance not available: {e}{RESET}")
        print(f"\n{YELLOW}Start it with:{RESET}")
        print("  docker compose -f docker-compose.pg-test.yml up -d\n")
        return False


def main():
    """Run PostgreSQL test suite and report results."""
    include_stress = "--stress" in sys.argv

    print(f"\n{BOLD}{BLUE}INtelliBOX PostgreSQL Test Suite{RESET}")
    print(f"{BLUE}Testing against PostgreSQL backend{RESET}\n")

    if not check_pg_available():
        return 1

    results = {}

    # Core tests
    for module in PG_TEST_MODULES:
        if not Path(module.rstrip("/")).exists():
            print(f"{YELLOW}  SKIP  {module} (not found){RESET}")
            continue
        success = run_test_module(module)
        results[module] = success

    # Performance tests
    for module in PG_PERF_MODULES:
        if not Path(module.rstrip("/")).exists():
            print(f"{YELLOW}  SKIP  {module} (not found){RESET}")
            continue
        success = run_test_module(module)
        results[module] = success

    # Stress tests (optional)
    if include_stress:
        print(f"\n{BOLD}{BLUE}Running stress/resilience/backup tests...{RESET}")
        for module in PG_STRESS_MODULES:
            if not Path(module.rstrip("/")).exists():
                print(f"{YELLOW}  SKIP  {module} (not found){RESET}")
                continue
            success = run_test_module(module)
            results[module] = success

    # Print summary
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}POSTGRESQL TEST SUMMARY{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    passed = sum(1 for success in results.values() if success)
    total = len(results)

    for module, success in results.items():
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f"  {status}  {module}")

    print(f"\n{BLUE}{'=' * 70}{RESET}")

    if total == 0:
        print(f"{YELLOW}No test modules found. Write tests first!{RESET}")
        return 0
    elif passed == total:
        print(f"{GREEN}{BOLD}All {total} PostgreSQL test modules passed!{RESET}")
        return 0
    else:
        print(f"{YELLOW}{BOLD}{passed}/{total} PostgreSQL test modules passed{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
