#!/usr/bin/env python3
"""
Web Interface Validation Script for EmailTools

This script validates that all web pages and features work correctly
with your actual database. Run this before deploying to ensure everything
functions properly for end users.

Usage:
    1. Start web server: emailtools web --host 127.0.0.1 --port 8000
    2. Run this script: python validate_web_interface.py
"""

import requests
import sys
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

BASE_URL = "http://127.0.0.1:8000"

def print_header(text):
    """Print a section header."""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}{text}")
    print(f"{Fore.CYAN}{'='*70}")

def print_success(text):
    """Print success message."""
    print(f"{Fore.GREEN}[OK] {text}")

def print_error(text):
    """Print error message."""
    print(f"{Fore.RED}[X] {text}")

def print_warning(text):
    """Print warning message."""
    print(f"{Fore.YELLOW}[!] {text}")

def print_info(text):
    """Print info message."""
    print(f"{Fore.BLUE}[i] {text}")

def test_page(name, url, expected_content=None, check_status=200):
    """Test a web page."""
    try:
        response = requests.get(f"{BASE_URL}{url}", timeout=10)

        if response.status_code != check_status:
            print_error(f"{name}: Expected HTTP {check_status}, got {response.status_code}")
            return False

        if expected_content:
            if isinstance(expected_content, list):
                missing = []
                for content in expected_content:
                    if content.encode() not in response.content:
                        missing.append(content)
                if missing:
                    print_error(f"{name}: Missing content: {', '.join(missing)}")
                    return False
            else:
                if expected_content.encode() not in response.content:
                    print_error(f"{name}: Missing expected content")
                    return False

        print_success(f"{name}: HTTP {response.status_code}")
        return True

    except requests.exceptions.ConnectionError:
        print_error(f"{name}: Cannot connect to server. Is it running?")
        return False
    except requests.exceptions.Timeout:
        print_error(f"{name}: Request timeout")
        return False
    except Exception as e:
        print_error(f"{name}: {str(e)}")
        return False

def test_api_endpoint(name, url):
    """Test an API endpoint and return JSON data."""
    try:
        response = requests.get(f"{BASE_URL}{url}", timeout=10)

        if response.status_code != 200:
            print_error(f"{name}: HTTP {response.status_code}")
            return None

        data = response.json()
        print_success(f"{name}: HTTP 200")
        return data

    except requests.exceptions.ConnectionError:
        print_error(f"{name}: Cannot connect to server")
        return None
    except Exception as e:
        print_error(f"{name}: {str(e)}")
        return None

def validate_web_interface():
    """Run all validation tests."""
    print_header("EmailTools Web Interface Validation")
    print(f"Testing server at: {BASE_URL}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    results = {
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }

    # Test 1: Health Check
    print_header("1. Health Check & API Endpoints")
    if test_page("Health Check", "/health"):
        results["passed"] += 1
    else:
        results["failed"] += 1
        print_error("CRITICAL: Health check failed. Server may not be running.")
        return results

    # Test 2: API Stats
    stats = test_api_endpoint("API Stats", "/api/stats")
    if stats:
        results["passed"] += 1
        print_info(f"  Total Emails: {stats.get('total_emails', 0)}")
        print_info(f"  Total Actions: {stats.get('total_actions', 0)}")
        print_info(f"  Unassigned Actions: {stats.get('unassigned_actions', 0)}")
        print_info(f"  High Priority: {stats.get('high_priority', 0)}")

        if stats.get('total_emails', 0) == 0:
            print_warning("No emails in database - some pages may be empty")
            results["warnings"] += 1
    else:
        results["failed"] += 1

    # Test 3: Main Pages
    print_header("2. Main Pages")

    pages = [
        ("Dashboard", "/", "Dashboard"),
        ("Actions List", "/actions", "Actions"),
        ("Emails List", "/emails", "Emails"),
        ("Daily Report", "/report", "Daily Report"),
    ]

    for name, url, expected in pages:
        if test_page(name, url, expected):
            results["passed"] += 1
        else:
            results["failed"] += 1

    # Test 4: Filtering & Pagination
    print_header("3. Filtering & Pagination")

    filters = [
        ("High Priority Filter", "/actions?priority=high"),
        ("Medium Priority Filter", "/actions?priority=medium"),
        ("Low Priority Filter", "/actions?priority=low"),
        ("Unassigned Filter", "/actions?assigned=false"),
        ("Assigned Filter", "/actions?assigned=true"),
        ("Pagination Page 1", "/actions?page=1"),
        ("Email Pagination", "/emails?page=1"),
    ]

    for name, url in filters:
        if test_page(name, url):
            results["passed"] += 1
        else:
            results["failed"] += 1

    # Test 5: Detail Pages (if data exists)
    print_header("4. Detail Pages")

    if stats and stats.get('total_actions', 0) > 0:
        # Get actions list to find a valid ID
        try:
            import re
            response = requests.get(f"{BASE_URL}/actions", timeout=10)
            if response.status_code == 200 and b'/actions/' in response.content:
                # Extract an action ID from the HTML
                match = re.search(rb'/actions/(\d+)', response.content)
                if match:
                    action_id = int(match.group(1))
                    response = requests.get(f"{BASE_URL}/actions/{action_id}", timeout=5)
                    if response.status_code == 200:
                        print_success(f"Action Detail (ID {action_id}): HTTP 200")
                        results["passed"] += 1
                    else:
                        print_warning("Action detail page returned non-200 status")
                        results["warnings"] += 1
                else:
                    print_warning("Could not extract action ID from actions page")
                    results["warnings"] += 1
            else:
                print_warning("Could not load actions page to find valid ID")
                results["warnings"] += 1
        except Exception as e:
            print_warning(f"Could not test action detail: {str(e)}")
            results["warnings"] += 1
    else:
        print_warning("No actions in database - skipping action detail test")
        results["warnings"] += 1

    if stats and stats.get('total_emails', 0) > 0:
        # Get emails list to find a valid ID
        try:
            import re
            response = requests.get(f"{BASE_URL}/emails", timeout=10)
            if response.status_code == 200 and b'/emails/' in response.content:
                # Extract an email ID from the HTML
                match = re.search(rb'/emails/(\d+)', response.content)
                if match:
                    email_id = int(match.group(1))
                    response = requests.get(f"{BASE_URL}/emails/{email_id}", timeout=5)
                    if response.status_code == 200:
                        print_success(f"Email Detail (ID {email_id}): HTTP 200")
                        results["passed"] += 1
                    else:
                        print_warning("Email detail page returned non-200 status")
                        results["warnings"] += 1
                else:
                    print_warning("Could not extract email ID from emails page")
                    results["warnings"] += 1
            else:
                print_warning("Could not load emails page to find valid ID")
                results["warnings"] += 1
        except Exception as e:
            print_warning(f"Could not test email detail: {str(e)}")
            results["warnings"] += 1
    else:
        print_warning("No emails in database - skipping email detail test")
        results["warnings"] += 1

    # Test 6: 404 Handling
    print_header("5. Error Handling")

    if test_page("Non-existent Action 404", "/actions/999999", check_status=404):
        results["passed"] += 1
    else:
        results["failed"] += 1

    if test_page("Non-existent Email 404", "/emails/999999", check_status=404):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # Print Summary
    print_header("Validation Summary")

    total = results["passed"] + results["failed"]
    pass_rate = (results["passed"] / total * 100) if total > 0 else 0

    print(f"\n{Fore.GREEN}Passed: {results['passed']}")
    print(f"{Fore.RED}Failed: {results['failed']}")
    print(f"{Fore.YELLOW}Warnings: {results['warnings']}")
    print(f"\n{Fore.CYAN}Pass Rate: {pass_rate:.1f}%")

    if results["failed"] == 0:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}[OK] ALL TESTS PASSED!")
        print(f"{Fore.GREEN}Web interface is ready for deployment.{Style.RESET_ALL}\n")
        return results
    else:
        print(f"\n{Fore.RED}{Style.BRIGHT}[X] SOME TESTS FAILED")
        print(f"{Fore.RED}Please fix the issues above before deploying.{Style.RESET_ALL}\n")
        return results

if __name__ == "__main__":
    print(f"""
{Fore.CYAN}EmailTools Web Interface Validator
{Fore.CYAN}==================================={Style.RESET_ALL}

This script validates all web pages and features.

{Fore.YELLOW}Prerequisites:{Style.RESET_ALL}
1. Web server must be running: emailtools web --host 127.0.0.1 --port 8000
2. Database should have some test data

{Fore.YELLOW}Note:{Style.RESET_ALL} First install required package: pip install colorama requests
""")

    try:
        results = validate_web_interface()

        # Exit with appropriate code
        sys.exit(0 if results["failed"] == 0 else 1)

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Validation interrupted by user{Style.RESET_ALL}")
        sys.exit(130)
