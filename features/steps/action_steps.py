"""
Action-specific Behave step definitions.
"""

from behave import given, when, then

from features.environment import query_action, query_assignment


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


@when('I quick-change the action priority to "{priority}"')
def step_quick_change_priority(context, priority):
    context.response = context.client.post(
        f"/actions/{context.last_action_id}/priority",
        data={"priority": priority},
        follow_redirects=False,
    )


@when("I quick-unassign the action")
def step_quick_unassign(context):
    context.response = context.client.post(
        f"/actions/{context.last_action_id}/unassign",
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
    data = query_action(context, context.last_action_id)
    assert data is not None
    assert data["has_assignments"], "Expected action to have assignments"


@then("the action has no assignment in the database")
def step_no_assignment(context):
    data = query_assignment(context, context.last_action_id)
    assert data is None or data.get("status") == "completed", \
        "Expected action to have no active assignment"


@then('the action is marked as "{status}" in the database')
def step_action_status_in_db(context, status):
    data = query_assignment(context, context.last_action_id)
    assert data is not None, "Expected an assignment record"
    assert data["status"] == status, f"Expected status={status}, got {data['status']}"


@then('the action priority is "{priority}" in the database')
def step_action_priority_in_db(context, priority):
    data = query_action(context, context.last_action_id)
    assert data is not None
    assert data["priority"] == priority, f"Expected priority={priority}, got {data['priority']}"


@then('the action title is "{title}" in the database')
def step_action_title_in_db(context, title):
    data = query_action(context, context.last_action_id)
    assert data is not None
    assert data["title"] == title, f"Expected title='{title}', got '{data['title']}'"


@then("the action has no due date in the database")
def step_action_no_due_date(context):
    data = query_action(context, context.last_action_id)
    assert data is not None
    assert data["due_date"] is None, f"Expected no due date, got {data['due_date']}"


@then('the action category is "{category}" in the database')
def step_action_category_in_db(context, category):
    data = query_action(context, context.last_action_id)
    assert data is not None
    assert data["category"] == category, f"Expected category='{category}', got '{data['category']}'"


@then("the action no longer exists in the database")
def step_action_deleted(context):
    data = query_action(context, context.last_action_id)
    assert data is None, "Expected action to be deleted"


@then('the action is assigned to "{assignee}" in the database')
def step_action_assignee_in_db(context, assignee):
    data = query_assignment(context, context.last_action_id)
    assert data is not None, "Expected an assignment record"
    assert data["assigned_to"] == assignee, (
        f"Expected assigned_to='{assignee}', got '{data['assigned_to']}'"
    )
