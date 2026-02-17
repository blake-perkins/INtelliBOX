"""
Settings, categories, and roster Behave step definitions.
"""

from behave import given, when, then

from emailtools.models import RosterMember
from emailtools.settings_service import SettingsService
from features.environment import make_session


@when("I add a category named {name}")
def step_add_category(context, name):
    context.response = context.client.post(
        "/categories/add",
        data={"name": name, "description": "A test category"},
        follow_redirects=False,
    )


@when("I delete the category named {name}")
def step_delete_category(context, name):
    context.response = context.client.post(
        "/categories/delete",
        data={"name": name},
        follow_redirects=False,
    )


@when("I save settings with data")
def step_save_settings(context):
    data = {row["field"]: row["value"] for row in context.table}
    context.response = context.client.post("/settings", data=data, follow_redirects=False)


@when('I add a roster member with first "{first}" last "{last}" email "{email}"')
def step_add_roster_member(context, first, last, email):
    context.response = context.client.post(
        "/roster/add",
        data={"first_name": first, "last_name": last, "email": email},
        follow_redirects=False,
    )


@when("I delete the roster member")
def step_delete_roster_member(context):
    context.response = context.client.post(
        f"/roster/{context.last_member_id}/delete",
        follow_redirects=False,
    )


@then("the settings page shows success")
def step_settings_success(context):
    assert context.response.status_code in (200, 303), (
        f"Expected 200 or 303, got {context.response.status_code}"
    )


@then("the roster member is saved in the database")
def step_member_in_db(context):
    session = make_session(context)
    count = session.query(RosterMember).count()
    assert count > 0, "Expected at least one roster member"
    session.close()


@then("the roster member is removed from the database")
def step_member_removed_from_db(context):
    session = make_session(context)
    member = session.query(RosterMember).filter_by(id=context.last_member_id).first()
    assert member is None, "Expected member to be deleted"
    session.close()
