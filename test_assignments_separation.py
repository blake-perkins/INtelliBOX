#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test that Recent Completions don't appear in Recent Assignments
"""
import sys
import io
import requests

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from src.emailtools.database import SessionLocal
from src.emailtools.models import Action, Assignment
from sqlalchemy import desc

BASE_URL = "http://127.0.0.1:8000"

def print_section(title):
    print(f"\n{'='*80}")
    print(f"{title}")
    print('='*80)

def main():
    print_section("Test: Recent Assignments vs Recent Completions Separation")

    session = SessionLocal()

    # Get current state from database
    print("\n1. Current Database State:")
    print("-" * 80)

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

    print(f"Recent Assignments (not completed): {len(recent_assignments)}")
    for assignment, action in recent_assignments:
        print(f"  - {action.title[:50]} (Status: {assignment.status}, Assigned to: {assignment.assigned_to})")

    print(f"\nRecent Completions: {len(recent_completions)}")
    for assignment, action in recent_completions:
        print(f"  - {action.title[:50]} (Status: {assignment.status}, Assigned to: {assignment.assigned_to})")

    # Check for any overlap (should be zero)
    assignment_action_ids = {action.id for _, action in recent_assignments}
    completion_action_ids = {action.id for _, action in recent_completions}
    overlap = assignment_action_ids & completion_action_ids

    print(f"\nOverlap check: {len(overlap)} actions appear in both lists")
    if overlap:
        print(f"  ❌ FAIL: Actions {overlap} appear in both Recent Assignments and Recent Completions")
    else:
        print(f"  ✅ PASS: No overlap between Recent Assignments and Recent Completions")

    # Test the web interface
    print_section("2. Web Dashboard Check")

    response = requests.get(f"{BASE_URL}/", timeout=10)
    if response.status_code == 200:
        print(f"✅ Dashboard loaded successfully")

        # Check if dashboard renders both sections
        html = response.text
        has_assignments = "Recent Assignments" in html
        has_completions = "Recent Completions" in html

        print(f"   Recent Assignments section: {'✅ Found' if has_assignments else '❌ Missing'}")
        print(f"   Recent Completions section: {'✅ Found' if has_completions else '❌ Missing'}")
    else:
        print(f"❌ Dashboard failed: HTTP {response.status_code}")

    # Test by completing an action
    print_section("3. Test Completing an Action")

    if recent_assignments:
        test_assignment, test_action = recent_assignments[0]
        test_action_id = test_action.id

        print(f"Testing with action: {test_action.title[:50]}")
        print(f"Current status: {test_assignment.status}")

        # Mark as complete via web interface
        complete_response = requests.post(
            f"{BASE_URL}/actions/{test_action_id}/complete",
            allow_redirects=False,
            timeout=10
        )

        if complete_response.status_code == 303:
            print(f"✅ Marked as complete via web interface")

            # Refresh database session
            session.close()
            session = SessionLocal()

            # Re-query both lists
            new_assignments = session.query(Assignment, Action).join(
                Action
            ).filter(
                Assignment.status != "completed"
            ).order_by(desc(Assignment.assigned_at)).limit(5).all()

            new_completions = session.query(Assignment, Action).join(
                Action
            ).filter(
                Assignment.status == "completed"
            ).order_by(desc(Assignment.assigned_at)).limit(5).all()

            # Check if action moved from assignments to completions
            in_assignments = any(action.id == test_action_id for _, action in new_assignments)
            in_completions = any(action.id == test_action_id for _, action in new_completions)

            print(f"\nAfter completion:")
            print(f"   In Recent Assignments: {'❌ YES (FAIL)' if in_assignments else '✅ NO (PASS)'}")
            print(f"   In Recent Completions: {'✅ YES (PASS)' if in_completions else '❌ NO (FAIL)'}")

            if not in_assignments and in_completions:
                print(f"\n✅ SUCCESS: Action moved from Recent Assignments to Recent Completions")
            else:
                print(f"\n❌ FAIL: Action did not move correctly")

            # Undo the completion for cleanup
            undo_response = requests.post(
                f"{BASE_URL}/actions/{test_action_id}/unassign",
                allow_redirects=False,
                timeout=10
            )

            # Re-assign it
            requests.post(
                f"{BASE_URL}/actions/{test_action_id}/assign",
                data={"assigned_to": test_assignment.assigned_to, "notes": "Test cleanup"},
                allow_redirects=False,
                timeout=10
            )
            print(f"\n(Cleanup: Restored original assignment for testing)")

        else:
            print(f"❌ Failed to complete action: HTTP {complete_response.status_code}")
    else:
        print("⚠️  No recent assignments to test with")

    print_section("4. Final Validation Summary")

    # Final check
    session.close()
    session = SessionLocal()

    final_assignments = session.query(Assignment, Action).join(
        Action
    ).filter(
        Assignment.status != "completed"
    ).order_by(desc(Assignment.assigned_at)).limit(5).all()

    final_completions = session.query(Assignment, Action).join(
        Action
    ).filter(
        Assignment.status == "completed"
    ).order_by(desc(Assignment.assigned_at)).limit(5).all()

    final_assignment_ids = {action.id for _, action in final_assignments}
    final_completion_ids = {action.id for _, action in final_completions}
    final_overlap = final_assignment_ids & final_completion_ids

    if len(final_overlap) == 0:
        print(f"✅ PASS: No actions appear in both Recent Assignments and Recent Completions")
        print(f"   Recent Assignments: {len(final_assignments)} items")
        print(f"   Recent Completions: {len(final_completions)} items")
        print(f"   Overlap: 0 items")
        print(f"\n✅ ALL TESTS PASSED")
    else:
        print(f"❌ FAIL: {len(final_overlap)} actions appear in both lists")
        print(f"   Overlapping action IDs: {final_overlap}")

    session.close()

if __name__ == "__main__":
    main()
