"""
Common Behave step definitions: navigation, assertions, and test data setup.
"""

from behave import given, when, then
from datetime import datetime, timedelta

from emailtools.models import Email, Action, Assignment, RosterMember
from features.environment import make_session


# ---------------------------------------------------------------------------
# Data setup steps (Given)
# ---------------------------------------------------------------------------

@given("the database is empty")
def step_database_empty(context):
    # before_scenario already wiped tables; nothing to do
    pass


@given('an email exists with subject "{subject}"')
def step_email_exists(context, subject):
    session = make_session(context)
    email = Email(
        message_id=f"msg-{subject.lower().replace(' ', '-')}@test.com",
        subject=subject,
        from_address="sender@example.com",
        from_name="Test Sender",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=1),
        body_text=f"Body of email: {subject}",
        processed=True,
        processed_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()
    context.last_email = email
    context.last_email_id = email.id
    session.close()


@given("an overdue unassigned high priority action exists")
def step_overdue_action(context):
    session = make_session(context)
    email = Email(
        message_id="overdue-email@test.com",
        subject="Overdue Request",
        from_address="urgent@example.com",
        from_name="Urgent Sender",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=10),
        body_text="This needed to be done a week ago.",
        processed=True,
        processed_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()
    action = Action(
        email_id=email.id,
        title="Overdue action item",
        description="This is past its due date",
        priority="high",
        due_date=datetime.utcnow() - timedelta(days=3),
        category="RFI",
        confidence_score=0.95,
    )
    session.add(action)
    session.commit()
    context.last_action_id = action.id
    session.close()


@given('an unassigned "{priority}" priority action exists with title "{title}"')
def step_action_exists_unassigned(context, priority, title):
    session = make_session(context)
    email = Email(
        message_id=f"email-for-{title.lower().replace(' ', '-')}@test.com",
        subject=f"Subject for {title}",
        from_address="sender@example.com",
        from_name="Sender",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=1),
        body_text="Email body.",
        processed=True,
        processed_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()
    action = Action(
        email_id=email.id,
        title=title,
        description=f"Description for {title}",
        priority=priority,
        due_date=datetime.utcnow() + timedelta(days=5),
        category="RFI",
        confidence_score=0.9,
    )
    session.add(action)
    session.commit()
    context.last_action_id = action.id
    context.last_email_id = email.id
    session.close()


@given('an action titled "{title}" is assigned to "{assignee}"')
def step_action_assigned(context, title, assignee):
    session = make_session(context)
    email = Email(
        message_id=f"email-assigned-{title.lower().replace(' ', '-')}@test.com",
        subject=f"Subject for {title}",
        from_address="sender@example.com",
        from_name="Sender",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=1),
        body_text="Email body.",
        processed=True,
        processed_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()
    action = Action(
        email_id=email.id,
        title=title,
        description=f"Description for {title}",
        priority="medium",
        due_date=datetime.utcnow() + timedelta(days=5),
        category="RFI",
        confidence_score=0.9,
    )
    session.add(action)
    session.commit()
    assignment = Assignment(
        action_id=action.id,
        assigned_to=assignee,
        status="assigned",
        notes="",
    )
    session.add(assignment)
    session.commit()
    context.last_action_id = action.id
    context.last_email_id = email.id
    session.close()


@given('a completed action titled "{title}" exists')
def step_completed_action(context, title):
    session = make_session(context)
    email = Email(
        message_id=f"email-completed-{title.lower().replace(' ', '-')}@test.com",
        subject=f"Subject for {title}",
        from_address="sender@example.com",
        from_name="Sender",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=2),
        body_text="Email body.",
        processed=True,
        processed_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()
    action = Action(
        email_id=email.id,
        title=title,
        description=f"Description for {title}",
        priority="medium",
        due_date=datetime.utcnow() + timedelta(days=5),
        category="RFI",
        confidence_score=0.9,
    )
    session.add(action)
    session.commit()
    assignment = Assignment(
        action_id=action.id,
        assigned_to="someone@example.com",
        status="completed",
        notes="Done",
    )
    session.add(assignment)
    session.commit()
    context.last_action_id = action.id
    context.last_email_id = email.id
    session.close()


@given('an unassigned "{priority}" priority action exists for the same email with title "{title}"')
def step_action_same_email(context, priority, title):
    session = make_session(context)
    action = Action(
        email_id=context.last_email_id,
        title=title,
        description=f"Description for {title}",
        priority=priority,
        due_date=datetime.utcnow() + timedelta(days=5),
        category="RFI",
        confidence_score=0.9,
    )
    session.add(action)
    session.commit()
    # Don't overwrite last_action_id — keep the first one
    session.close()


@given('an overdue assigned action titled "{title}" is assigned to "{assignee}"')
def step_overdue_assigned_action(context, title, assignee):
    session = make_session(context)
    email = Email(
        message_id=f"email-overdue-assigned-{title.lower().replace(' ', '-')}@test.com",
        subject=f"Subject for {title}",
        from_address="sender@example.com",
        from_name="Sender",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=10),
        body_text="Email body.",
        processed=True,
        processed_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()
    action = Action(
        email_id=email.id,
        title=title,
        description=f"Description for {title}",
        priority="high",
        due_date=datetime.utcnow() - timedelta(days=3),
        category="RFI",
        confidence_score=0.9,
    )
    session.add(action)
    session.commit()
    assignment = Assignment(
        action_id=action.id,
        assigned_to=assignee,
        status="assigned",
        notes="",
    )
    session.add(assignment)
    session.commit()
    context.last_action_id = action.id
    context.last_email_id = email.id
    session.close()


@given('an unprocessed email exists with subject "{subject}"')
def step_unprocessed_email(context, subject):
    session = make_session(context)
    email = Email(
        message_id=f"msg-unprocessed-{subject.lower().replace(' ', '-')}@test.com",
        subject=subject,
        from_address="sender@example.com",
        from_name="Test Sender",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=1),
        body_text=f"Body of email: {subject}",
        processed=False,
    )
    session.add(email)
    session.commit()
    context.last_email = email
    context.last_email_id = email.id
    session.close()


@given('a roster member "{first}" "{last}" with email "{email}" exists')
def step_roster_member_exists(context, first, last, email):
    session = make_session(context)
    member = RosterMember(
        first_name=first,
        last_name=last,
        email=email,
    )
    session.add(member)
    session.commit()
    context.last_member_id = member.id
    session.close()


# ---------------------------------------------------------------------------
# Navigation steps (When)
# ---------------------------------------------------------------------------

@when('I navigate to "{path}"')
def step_navigate(context, path):
    context.response = context.client.get(path)


@when("I navigate to the action detail page")
def step_navigate_action_detail(context):
    context.response = context.client.get(f"/actions/{context.last_action_id}")


@when("I navigate to the email detail page")
def step_navigate_email_detail(context):
    context.response = context.client.get(f"/emails/{context.last_email_id}")


@when("I navigate to the create action form for that email")
def step_navigate_create_action_form(context):
    context.response = context.client.get(f"/emails/{context.last_email_id}/actions/new")


# ---------------------------------------------------------------------------
# POST steps (When)
# ---------------------------------------------------------------------------

@when("I submit a POST to {path} with data")
def step_post_with_table(context, path):
    data = {row["field"]: row["value"] for row in context.table}
    context.response = context.client.post(path, data=data, follow_redirects=False)


@when('I POST to "{path}"')
def step_post_to(context, path):
    context.response = context.client.post(path, follow_redirects=False)


# ---------------------------------------------------------------------------
# Assertion steps (Then)
# ---------------------------------------------------------------------------

@then("the response status is {code:d}")
def step_status(context, code):
    assert context.response.status_code == code, (
        f"Expected {code}, got {context.response.status_code}"
    )


@then('the page contains "{text}"')
def step_contains(context, text):
    assert text.encode() in context.response.content, (
        f"Expected to find '{text}' in response"
    )


@then('the page does not contain "{text}"')
def step_not_contains(context, text):
    assert text.encode() not in context.response.content, (
        f"Did not expect to find '{text}' in response"
    )


@then("the response is a redirect")
def step_is_redirect(context):
    assert context.response.status_code in (301, 302, 303, 307, 308), (
        f"Expected redirect, got {context.response.status_code}"
    )


@then("the JSON field {field} equals {expected}")
def step_json_field_equals(context, field, expected):
    data = context.response.json()
    actual = data[field]
    # Try to cast expected to int if numeric
    try:
        expected = int(expected)
    except (ValueError, TypeError):
        pass
    assert actual == expected, f"Expected {field}={expected}, got {actual}"


@then("the JSON field {field} is greater than {expected:d}")
def step_json_field_gt(context, field, expected):
    data = context.response.json()
    assert data[field] > expected, f"Expected {field}>{expected}, got {data[field]}"
