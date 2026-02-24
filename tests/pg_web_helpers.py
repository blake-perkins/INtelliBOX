"""Shared test data factory for web route tests (SQLite and PostgreSQL)."""

from datetime import datetime, timedelta

from intellibox.models import Action, Assignment, Email, RosterMember


def populate_test_data(session_factory, *, include_roster=True):
    """Create standard test dataset and return entity IDs.

    Creates: 3 emails, 4 actions, 1 assignment, and optionally 2 roster members.
    Returns a dict of IDs for test assertions.
    """
    session = session_factory()

    now = datetime.utcnow()

    # Emails
    email1 = Email(
        message_id="test1@example.com",
        subject="Test RFI - Budget Data Request",
        from_address="boss@example.com",
        from_name="Boss Man",
        to_addresses='["team@example.com"]',
        received_date=now - timedelta(days=1),
        body_text="Please provide the budget data by Friday.",
        processed=True,
        processed_at=now,
    )
    email2 = Email(
        message_id="test2@example.com",
        subject="URGENT: Production Issue",
        from_address="alerts@monitoring.com",
        from_name="Alert System",
        to_addresses='["team@example.com"]',
        received_date=now - timedelta(hours=2),
        body_text="Critical error in production. Investigate immediately.",
        processed=True,
        processed_at=now,
    )
    email3 = Email(
        message_id="test3@example.com",
        subject="Meeting Notes",
        from_address="colleague@example.com",
        from_name="Colleague",
        to_addresses='["team@example.com"]',
        received_date=now - timedelta(days=3),
        body_text="Here are the notes from yesterday's meeting.",
        processed=True,
        processed_at=now,
    )

    session.add_all([email1, email2, email3])
    session.commit()

    # Actions
    action1 = Action(
        email_id=email1.id,
        title="Provide budget data",
        description="Compile and send budget data to boss",
        priority="high",
        due_date=now + timedelta(days=3),
        category="RFI",
        confidence_score=0.95,
    )
    action2 = Action(
        email_id=email2.id,
        title="Investigate production error",
        description="Check logs and identify root cause",
        priority="high",
        due_date=now + timedelta(hours=4),
        category="incident",
        confidence_score=0.98,
    )
    action3 = Action(
        email_id=email3.id,
        title="Review meeting notes",
        description="Read and follow up on action items from meeting",
        priority="medium",
        due_date=now + timedelta(days=7),
        category="follow-up",
        confidence_score=0.75,
    )
    action4 = Action(
        email_id=email1.id,
        title="Schedule follow-up meeting",
        description="Set up meeting to discuss budget",
        priority="low",
        due_date=None,
        category="meeting",
        confidence_score=0.60,
    )

    session.add_all([action1, action2, action3, action4])
    session.commit()

    # Assignment (action1 is assigned)
    assignment1 = Assignment(
        action_id=action1.id,
        assigned_to="john@example.com",
        status="assigned",
        notes="Working on it",
    )
    session.add(assignment1)
    session.commit()

    ids = {
        "email1": email1.id,
        "email2": email2.id,
        "email3": email3.id,
        "action1": action1.id,
        "action2": action2.id,
        "action3": action3.id,
        "action4": action4.id,
        "assignment1": assignment1.id,
    }

    # Roster members (optional — some tests need an empty roster)
    if include_roster:
        roster1 = RosterMember(
            first_name="Alice", last_name="Smith", email="alice@example.com"
        )
        roster2 = RosterMember(
            first_name="Bob", last_name="Jones", email="bob@example.com"
        )
        session.add_all([roster1, roster2])
        session.commit()
        ids["roster1"] = roster1.id
        ids["roster2"] = roster2.id

    session.close()
    return ids
