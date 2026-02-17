"""
Action-specific Behave step definitions.
"""

from behave import given, when, then
from datetime import datetime, timedelta

from emailtools.models import Email, Action, Assignment
from features.environment import make_session


@when('I assign the action to "{assignee}"')
def step_assign_action(context, assignee):
    context.response = context.client.post(
        f"/actions/{context.last_action_id}/assign",
        data={"assigned_to": assignee},
        follow_redirects=False,
    )



@when("I mark the action as complete")
def step_complete_action(context):
    context.response = context.client.post(
        f"/actions/{context.last_action_id}/complete",
        follow_redirects=False,
    )


@when('I change the action status to "{status}"')
def step_change_status(context, status):
    context.response = context.client.post(
        f"/actions/{context.last_action_id}/status",
        data={"status": status},
        follow_redirects=False,
    )


@when("I delete the action")
def step_delete_action(context):
    context.response = context.client.post(
        f"/actions/{context.last_action_id}/delete",
        follow_redirects=False,
    )


@when('I create a new action for that email with title "{title}"')
def step_create_action_minimal(context, title):
    context.response = context.client.post(
        f"/emails/{context.last_email_id}/actions/new",
        data={"title": title, "priority": "medium"},
        follow_redirects=False,
    )


@when("I save a full edit form for the action")
def step_save_full_edit_form(context):
    data = {row["field"]: row["value"] for row in context.table}
    context.response = context.client.post(
        f"/actions/{context.last_action_id}/edit",
        data=data,
        follow_redirects=False,
    )


@when("I create a new action with all fields")
def step_create_action_full(context):
    data = {row["field"]: row["value"] for row in context.table}
    context.response = context.client.post(
        f"/emails/{context.last_email_id}/actions/new",
        data=data,
        follow_redirects=False,
    )


@then("the action assignment is saved in the database")
def step_assignment_saved(context):
    session = make_session(context)
    action = session.query(Action).filter_by(id=context.last_action_id).first()
    assert action is not None
    assert action.assignments is not None and len(action.assignments) > 0
    session.close()


@then("the action has no assignment in the database")
def step_no_assignment(context):
    session = make_session(context)
    assignment = (
        session.query(Assignment)
        .filter_by(action_id=context.last_action_id)
        .filter(Assignment.status != "completed")
        .first()
    )
    assert assignment is None, "Expected action to have no active assignment"
    session.close()


@then('the action is marked as "{status}" in the database')
def step_action_status_in_db(context, status):
    session = make_session(context)
    assignment = (
        session.query(Assignment)
        .filter_by(action_id=context.last_action_id)
        .first()
    )
    assert assignment is not None, "Expected an assignment record"
    assert assignment.status == status, f"Expected status={status}, got {assignment.status}"
    session.close()


@then('the action priority is "{priority}" in the database')
def step_action_priority_in_db(context, priority):
    session = make_session(context)
    action = session.query(Action).filter_by(id=context.last_action_id).first()
    assert action.priority == priority, f"Expected priority={priority}, got {action.priority}"
    session.close()
