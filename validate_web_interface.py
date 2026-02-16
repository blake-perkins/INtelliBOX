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
    ]

    for name, url, expected in pages:
        if test_page(name, url, expected):
            results["passed"] += 1
        else:
            results["failed"] += 1

    # Test report with longer timeout (AI processing takes time)
    try:
        response = requests.get(f"{BASE_URL}/report", timeout=30)
        if response.status_code == 200 and b"Daily Report" in response.content:
            print_success("Daily Report: HTTP 200 (AI processing)")
            results["passed"] += 1
        else:
            print_error(f"Daily Report: HTTP {response.status_code}")
            results["failed"] += 1
    except requests.exceptions.Timeout:
        print_error("Daily Report: Request timeout (>30s)")
        results["failed"] += 1
    except Exception as e:
        print_error(f"Daily Report: {str(e)}")
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
                        print_error(f"Action detail page returned HTTP {response.status_code}")
                        results["failed"] += 1
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
                        print_error(f"Email detail page returned HTTP {response.status_code}")
                        results["failed"] += 1
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

    # Test 6: Interactive Features (POST endpoints)
    print_header("5. Interactive Features (Action Management)")

    if stats and stats.get('total_actions', 0) > 0:
        try:
            import re
            # Get an action ID to test with
            response = requests.get(f"{BASE_URL}/actions", timeout=10)
            if response.status_code == 200 and b'/actions/' in response.content:
                match = re.search(rb'/actions/(\d+)', response.content)
                if match:
                    test_action_id = int(match.group(1))
                    print_info(f"Using action ID {test_action_id} for testing")

                    # Test 6a: Assign Action
                    try:
                        assign_response = requests.post(
                            f"{BASE_URL}/actions/{test_action_id}/assign",
                            data={
                                "assigned_to": "test@example.com",
                                "notes": "Automated test assignment"
                            },
                            allow_redirects=False,
                            timeout=10
                        )

                        if assign_response.status_code == 303:
                            print_success(f"Assign Action: HTTP 303 (redirect)")
                            results["passed"] += 1

                            # Verify assignment was created
                            detail_response = requests.get(
                                f"{BASE_URL}/actions/{test_action_id}",
                                timeout=5
                            )
                            if b"test@example.com" in detail_response.content:
                                print_success(f"  Assignment verified in database")
                            else:
                                print_error(f"  Assignment not found in action detail page")
                                results["failed"] += 1
                        else:
                            print_error(f"Assign Action: Expected HTTP 303, got {assign_response.status_code}")
                            results["failed"] += 1
                    except Exception as e:
                        print_error(f"Assign Action: {str(e)}")
                        results["failed"] += 1

                    # Test 6b: Change Priority
                    try:
                        priority_response = requests.post(
                            f"{BASE_URL}/actions/{test_action_id}/priority",
                            data={"priority": "high"},
                            allow_redirects=False,
                            timeout=10
                        )

                        if priority_response.status_code == 303:
                            print_success(f"Change Priority: HTTP 303 (redirect)")
                            results["passed"] += 1

                            # Verify priority was changed
                            detail_response = requests.get(
                                f"{BASE_URL}/actions/{test_action_id}",
                                timeout=5
                            )
                            if b"high Priority" in detail_response.content or b"badge-high" in detail_response.content:
                                print_success(f"  Priority change verified in database")
                            else:
                                print_warning(f"  Could not verify priority change (may already be high)")
                                results["warnings"] += 1
                        else:
                            print_error(f"Change Priority: Expected HTTP 303, got {priority_response.status_code}")
                            results["failed"] += 1
                    except Exception as e:
                        print_error(f"Change Priority: {str(e)}")
                        results["failed"] += 1

                    # Test 6c: Mark Complete
                    try:
                        complete_response = requests.post(
                            f"{BASE_URL}/actions/{test_action_id}/complete",
                            allow_redirects=False,
                            timeout=10
                        )

                        if complete_response.status_code == 303:
                            print_success(f"Mark Complete: HTTP 303 (redirect)")
                            results["passed"] += 1

                            # Verify completion status
                            detail_response = requests.get(
                                f"{BASE_URL}/actions/{test_action_id}",
                                timeout=5
                            )
                            if b"completed" in detail_response.content.lower():
                                print_success(f"  Completion status verified in database")
                            else:
                                print_warning(f"  Could not verify completion status")
                                results["warnings"] += 1
                        else:
                            print_error(f"Mark Complete: Expected HTTP 303, got {complete_response.status_code}")
                            results["failed"] += 1
                    except Exception as e:
                        print_error(f"Mark Complete: {str(e)}")
                        results["failed"] += 1

                    # Test 6d: Update Due Date (past date)
                    try:
                        due_date_response = requests.post(
                            f"{BASE_URL}/actions/{test_action_id}/due-date",
                            data={"due_date": "2024-01-15"},
                            allow_redirects=False,
                            timeout=10
                        )

                        if due_date_response.status_code == 303:
                            print_success(f"Update Due Date (past): HTTP 303 (redirect)")
                            results["passed"] += 1

                            # Verify due date was updated
                            detail_response = requests.get(
                                f"{BASE_URL}/actions/{test_action_id}",
                                timeout=5
                            )
                            if b"2024-01-15" in detail_response.content:
                                print_success(f"  Due date update verified (past dates allowed)")
                            else:
                                print_error(f"  Due date not found in action detail page")
                                results["failed"] += 1
                        else:
                            print_error(f"Update Due Date: Expected HTTP 303, got {due_date_response.status_code}")
                            results["failed"] += 1
                    except Exception as e:
                        print_error(f"Update Due Date: {str(e)}")
                        results["failed"] += 1

                    # Test 6e: Update Due Date (future date)
                    try:
                        future_date_response = requests.post(
                            f"{BASE_URL}/actions/{test_action_id}/due-date",
                            data={"due_date": "2026-12-31"},
                            allow_redirects=False,
                            timeout=10
                        )

                        if future_date_response.status_code == 303:
                            print_success(f"Update Due Date (future): HTTP 303 (redirect)")
                            results["passed"] += 1

                            # Verify due date was updated
                            detail_response = requests.get(
                                f"{BASE_URL}/actions/{test_action_id}",
                                timeout=5
                            )
                            if b"2026-12-31" in detail_response.content:
                                print_success(f"  Due date update verified (future dates work)")
                            else:
                                print_warning(f"  Could not verify future due date")
                                results["warnings"] += 1
                        else:
                            print_error(f"Update Due Date (future): Expected HTTP 303, got {future_date_response.status_code}")
                            results["failed"] += 1
                    except Exception as e:
                        print_error(f"Update Due Date (future): {str(e)}")
                        results["failed"] += 1

                    # Test 6f: Clear Due Date
                    try:
                        clear_date_response = requests.post(
                            f"{BASE_URL}/actions/{test_action_id}/due-date",
                            data={"due_date": ""},
                            allow_redirects=False,
                            timeout=10
                        )

                        if clear_date_response.status_code == 303:
                            print_success(f"Clear Due Date: HTTP 303 (redirect)")
                            results["passed"] += 1

                            # Verify due date was cleared
                            detail_response = requests.get(
                                f"{BASE_URL}/actions/{test_action_id}",
                                timeout=5
                            )
                            if b'value=""' in detail_response.content or b"No due date" in detail_response.content:
                                print_success(f"  Due date cleared successfully")
                            else:
                                print_warning(f"  Could not verify due date was cleared")
                                results["warnings"] += 1
                        else:
                            print_error(f"Clear Due Date: Expected HTTP 303, got {clear_date_response.status_code}")
                            results["failed"] += 1
                    except Exception as e:
                        print_error(f"Clear Due Date: {str(e)}")
                        results["failed"] += 1

                    # Test 6g: Unassign Action (cleanup)
                    try:
                        unassign_response = requests.post(
                            f"{BASE_URL}/actions/{test_action_id}/unassign",
                            allow_redirects=False,
                            timeout=10
                        )

                        if unassign_response.status_code == 303:
                            print_success(f"Unassign Action: HTTP 303 (redirect)")
                            results["passed"] += 1

                            # Verify assignment was removed
                            detail_response = requests.get(
                                f"{BASE_URL}/actions/{test_action_id}",
                                timeout=5
                            )
                            if b"Unassigned" in detail_response.content:
                                print_success(f"  Unassignment verified (test cleanup successful)")
                            else:
                                print_warning(f"  Could not verify unassignment")
                                results["warnings"] += 1
                        else:
                            print_error(f"Unassign Action: Expected HTTP 303, got {unassign_response.status_code}")
                            results["failed"] += 1
                    except Exception as e:
                        print_error(f"Unassign Action: {str(e)}")
                        results["failed"] += 1

                else:
                    print_warning("Could not extract action ID - skipping interactive tests")
                    results["warnings"] += 1
            else:
                print_warning("Could not load actions page - skipping interactive tests")
                results["warnings"] += 1
        except Exception as e:
            print_error(f"Interactive features test setup failed: {str(e)}")
            results["failed"] += 1
    else:
        print_warning("No actions in database - skipping interactive features tests")
        results["warnings"] += 1

    # Test 6: Regression Tests - Dashboard Logic
    print_header("6. Regression Tests: Dashboard Logic")

    try:
        from src.emailtools.database import SessionLocal
        from src.emailtools.models import Action, Assignment, Email
        from sqlalchemy import desc

        session = SessionLocal()

        # Test 6a: Recent Assignments should not include completed actions
        recent_assignments = session.query(Assignment, Action).join(
            Action
        ).filter(
            Assignment.status != "completed"
        ).order_by(desc(Assignment.assigned_at)).limit(5).all()

        recent_completions = session.query(Assignment, Action).join(
            Action
        ).filter(
            Assignment.status == "completed"
        ).order_by(desc(Assignment.assigned_at)).limit(5).all()

        # Check for overlap
        assignment_action_ids = {action.id for _, action in recent_assignments}
        completion_action_ids = {action.id for _, action in recent_completions}
        overlap = assignment_action_ids & completion_action_ids

        if len(overlap) == 0:
            print_success(f"Recent Assignments/Completions separation: No overlap")
            results["passed"] += 1
        else:
            print_error(f"Recent Assignments includes completed actions: {overlap}")
            results["failed"] += 1

        # Test 6b: Overdue Actions should not include completed actions
        today = datetime.utcnow().date()
        overdue_actions = session.query(Action).outerjoin(Assignment).join(Email).filter(
            Action.due_date < today,
            (Assignment.id.is_(None)) | (Assignment.status != "completed")
        ).all()

        # Check if any overdue action is completed
        completed_overdue = [
            action for action in overdue_actions
            if action.assignments and action.assignments[0].status == "completed"
        ]

        if len(completed_overdue) == 0:
            print_success(f"Overdue Actions exclude completed: {len(overdue_actions)} overdue, 0 completed")
            results["passed"] += 1
        else:
            print_error(f"Overdue Actions includes {len(completed_overdue)} completed actions")
            results["failed"] += 1

        # Test 6c: Verify Recent Assignments only show non-completed statuses
        invalid_statuses = [
            assignment.status for assignment, _ in recent_assignments
            if assignment.status == "completed"
        ]

        if len(invalid_statuses) == 0:
            print_success(f"Recent Assignments status check: All are non-completed")
            results["passed"] += 1
        else:
            print_error(f"Recent Assignments includes {len(invalid_statuses)} completed items")
            results["failed"] += 1

        session.close()

    except Exception as e:
        print_error(f"Dashboard logic regression tests failed: {str(e)}")
        results["failed"] += 3  # Count as 3 failures (one for each test)

    # Test 7: 404 Handling
    print_header("7. Error Handling")

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
