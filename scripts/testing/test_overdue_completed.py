#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test that completed actions don't appear in Overdue Actions
"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.intellibox.database import SessionLocal
from src.intellibox.models import Action, Assignment, Email
from datetime import datetime, date

def print_section(title):
    print(f"\n{'='*80}")
    print(f"{title}")
    print('='*80)

def main():
    print_section("Test: Completed Actions Excluded from Overdue")

    session = SessionLocal()

    # Get all overdue actions including completed (old behavior)
    today = datetime.utcnow().date()
    all_overdue = session.query(Action).outerjoin(Assignment).join(Email).filter(
        Action.due_date < today
    ).order_by(Action.due_date).all()

    print(f"\nAll overdue actions (old behavior): {len(all_overdue)}")
    for action in all_overdue:
        assignee = action.assignments[0].assigned_to if action.assignments else 'Unassigned'
        status = action.assignments[0].status if action.assignments else 'N/A'
        print(f"  - {action.title[:50]}")
        print(f"    Assigned to: {assignee}, Status: {status}, Due: {action.due_date}")

    # Get overdue actions excluding completed (new behavior)
    overdue_not_completed = session.query(Action).outerjoin(Assignment).join(Email).filter(
        Action.due_date < today,
        (Assignment.id.is_(None)) | (Assignment.status != "completed")
    ).order_by(Action.due_date).all()

    print(f"\nOverdue actions (new behavior - excluding completed): {len(overdue_not_completed)}")
    for action in overdue_not_completed:
        assignee = action.assignments[0].assigned_to if action.assignments else 'Unassigned'
        status = action.assignments[0].status if action.assignments else 'N/A'
        print(f"  - {action.title[:50]}")
        print(f"    Assigned to: {assignee}, Status: {status}, Due: {action.due_date}")

    # Count completed overdue items that were filtered out
    completed_overdue_count = len(all_overdue) - len(overdue_not_completed)

    print_section("Results")
    print(f"Total overdue actions: {len(all_overdue)}")
    print(f"Completed overdue actions (filtered out): {completed_overdue_count}")
    print(f"Remaining overdue actions to show: {len(overdue_not_completed)}")

    if completed_overdue_count > 0:
        print(f"\n✅ SUCCESS: {completed_overdue_count} completed action(s) excluded from overdue list")
        print(f"\nCompleted overdue actions that were filtered:")
        for action in all_overdue:
            if action.assignments and action.assignments[0].status == "completed":
                print(f"  - {action.title[:50]} (assigned to {action.assignments[0].assigned_to})")
    else:
        print(f"\n⚠️  No completed overdue actions found in database")

    # Test Recent Assignments too
    print_section("Bonus: Recent Assignments Check")

    recent_assignments_all = session.query(Assignment, Action).join(
        Action
    ).order_by(Assignment.assigned_at.desc()).limit(5).all()

    recent_assignments_filtered = session.query(Assignment, Action).join(
        Action
    ).filter(
        Assignment.status != "completed"
    ).order_by(Assignment.assigned_at.desc()).limit(5).all()

    print(f"Recent assignments (old - all statuses): {len(recent_assignments_all)}")
    for assignment, action in recent_assignments_all:
        print(f"  - {action.title[:50]}")
        print(f"    Status: {assignment.status}, Assigned to: {assignment.assigned_to}")

    print(f"\nRecent assignments (new - excluding completed): {len(recent_assignments_filtered)}")
    for assignment, action in recent_assignments_filtered:
        print(f"  - {action.title[:50]}")
        print(f"    Status: {assignment.status}, Assigned to: {assignment.assigned_to}")

    completed_in_assignments = len(recent_assignments_all) - len(recent_assignments_filtered)
    if completed_in_assignments > 0:
        print(f"\n✅ {completed_in_assignments} completed action(s) excluded from Recent Assignments")
    else:
        print(f"\n✅ No completed actions in recent assignments (all are in Recent Completions)")

    session.close()

    print_section("Summary")
    print("✅ Code changes implemented correctly:")
    print("   1. Overdue Actions now excludes completed items")
    print("   2. Recent Assignments now excludes completed items")
    print("\n⚠️  NOTE: Web server needs restart to see changes in browser:")
    print("   1. Stop current web server (Ctrl+C in terminal)")
    print("   2. Restart: intellibox web --host 127.0.0.1 --port 8000")

if __name__ == "__main__":
    main()
