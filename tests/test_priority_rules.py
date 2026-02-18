"""Tests for PriorityRuleEngine."""

import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import intellibox.settings_service as settings_service_module
from intellibox import database as database_module

# Import models first to ensure they're registered with Base
from intellibox.models import Base, Settings

# Create a unique temporary database file for this test module
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_priority_rules.db', prefix='test_intellibox_')
TEST_DATABASE_URL = f"sqlite:///{test_db_path}"
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, isolation_level="READ UNCOMMITTED")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@contextmanager
def override_get_session():
    """Override database session for testing."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


# Patch get_session in both modules BEFORE importing anything that uses them
database_module.get_session = override_get_session
settings_service_module.get_session = override_get_session

# Now safe to import these
from intellibox.priority_rules import PriorityRuleEngine
from intellibox.settings_service import SettingsService


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """Create tables once for all tests in this module."""
    Base.metadata.create_all(bind=test_engine)
    yield
    # Clean up: close connections and remove temp database file
    test_engine.dispose()
    os.close(test_db_fd)
    os.unlink(test_db_path)


@pytest.fixture(scope="function")
def setup_database():
    """Clear data and set default settings before each test."""
    # Clear all settings
    with override_get_session() as session:
        session.query(Settings).delete()
        session.commit()

    # Set default priority settings for each test
    SettingsService.set_setting('priority_days_threshold', 5)
    SettingsService.set_setting('priority_high_senders', [])
    SettingsService.set_setting('priority_high_keywords', [])
    SettingsService.set_setting('priority_default', 'medium')

    yield

    # Clean up after test
    with override_get_session() as session:
        session.query(Settings).delete()
        session.commit()


def test_no_rules_keeps_ai_priority(setup_database):
    """Test that when no rules match, AI priority is preserved."""
    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Regular email',
        email_body='This is a normal email',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'low'


def test_high_priority_sender_match_full_email(setup_database):
    """Test that full email address match triggers high priority."""
    SettingsService.set_setting('priority_high_senders', ['customer@company.com'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='customer@company.com',
        email_subject='Request',
        email_body='Please help',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_high_priority_sender_match_domain(setup_database):
    """Test that domain match (e.g., @company.com) triggers high priority."""
    SettingsService.set_setting('priority_high_senders', ['@vip-client.com'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='anyone@vip-client.com',
        email_subject='Request',
        email_body='Please help',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_high_priority_sender_match_partial_domain(setup_database):
    """Test that partial domain match triggers high priority."""
    SettingsService.set_setting('priority_high_senders', ['importantclient.com'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='user@importantclient.com',
        email_subject='Request',
        email_body='Please help',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_high_priority_sender_case_insensitive(setup_database):
    """Test that sender matching is case-insensitive."""
    SettingsService.set_setting('priority_high_senders', ['customer@company.com'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='CUSTOMER@COMPANY.COM',
        email_subject='Request',
        email_body='Please help',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_high_priority_keyword_in_subject(setup_database):
    """Test that keyword in subject triggers high priority."""
    SettingsService.set_setting('priority_high_keywords', ['URGENT', 'CRITICAL'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='URGENT: Need response',
        email_body='This is urgent',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_high_priority_keyword_in_body(setup_database):
    """Test that keyword in body triggers high priority."""
    SettingsService.set_setting('priority_high_keywords', ['URGENT', 'CRITICAL'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Request',
        email_body='This is a CRITICAL issue that needs attention',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_high_priority_keyword_case_insensitive(setup_database):
    """Test that keyword matching is case-insensitive."""
    SettingsService.set_setting('priority_high_keywords', ['urgent'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='URGENT matter',
        email_body='Please respond',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_due_date_within_threshold(setup_database):
    """Test that due date within threshold triggers high priority."""
    SettingsService.set_setting('priority_days_threshold', 5)

    # Due in 3 days
    due_date = datetime.utcnow() + timedelta(days=3)

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Task',
        email_body='Complete this task',
        due_date=due_date,
        ai_priority='low'
    )
    assert priority == 'high'


def test_due_date_at_threshold_boundary(setup_database):
    """Test that due date exactly at threshold triggers high priority."""
    SettingsService.set_setting('priority_days_threshold', 5)

    # Due in exactly 5 days
    due_date = datetime.utcnow() + timedelta(days=5)

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Task',
        email_body='Complete this task',
        due_date=due_date,
        ai_priority='low'
    )
    assert priority == 'high'


def test_due_date_beyond_threshold(setup_database):
    """Test that due date beyond threshold does not trigger high priority."""
    SettingsService.set_setting('priority_days_threshold', 5)

    # Due in 10 days
    due_date = datetime.utcnow() + timedelta(days=10)

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Task',
        email_body='Complete this task',
        due_date=due_date,
        ai_priority='low'
    )
    assert priority == 'low'  # Keeps AI priority


def test_past_due_date_triggers_high(setup_database):
    """Test that past due date triggers high priority."""
    SettingsService.set_setting('priority_days_threshold', 5)

    # Due 2 days ago
    due_date = datetime.utcnow() - timedelta(days=2)

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Task',
        email_body='Complete this task',
        due_date=due_date,
        ai_priority='low'
    )
    assert priority == 'high'


def test_default_priority_used_when_ai_priority_missing(setup_database):
    """Test that default priority is used when AI priority is None."""
    SettingsService.set_setting('priority_default', 'medium')

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Task',
        email_body='Do something',
        due_date=None,
        ai_priority=None
    )
    assert priority == 'medium'


def test_default_priority_used_when_ai_priority_invalid(setup_database):
    """Test that default priority is used when AI priority is invalid."""
    SettingsService.set_setting('priority_default', 'low')

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Task',
        email_body='Do something',
        due_date=None,
        ai_priority='invalid_priority'
    )
    assert priority == 'low'


def test_rule_precedence_sender_over_ai(setup_database):
    """Test that sender rule overrides AI priority."""
    SettingsService.set_setting('priority_high_senders', ['vip@company.com'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='vip@company.com',
        email_subject='Request',
        email_body='Need help',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_rule_precedence_keyword_over_ai(setup_database):
    """Test that keyword rule overrides AI priority."""
    SettingsService.set_setting('priority_high_keywords', ['CRITICAL'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='CRITICAL issue',
        email_body='Fix this',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_rule_precedence_due_date_over_ai(setup_database):
    """Test that due date rule overrides AI priority."""
    SettingsService.set_setting('priority_days_threshold', 5)

    due_date = datetime.utcnow() + timedelta(days=2)

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Task',
        email_body='Complete soon',
        due_date=due_date,
        ai_priority='low'
    )
    assert priority == 'high'


def test_multiple_rules_first_match_wins(setup_database):
    """Test that when multiple rules match, the result is high priority."""
    SettingsService.set_setting('priority_high_senders', ['vip@company.com'])
    SettingsService.set_setting('priority_high_keywords', ['URGENT'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='vip@company.com',
        email_subject='URGENT request',
        email_body='Need help',
        due_date=None,
        ai_priority='low'
    )
    assert priority == 'high'


def test_empty_sender_list(setup_database):
    """Test that empty sender list doesn't crash."""
    SettingsService.set_setting('priority_high_senders', [])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='anyone@example.com',
        email_subject='Request',
        email_body='Help',
        due_date=None,
        ai_priority='medium'
    )
    assert priority == 'medium'


def test_empty_keyword_list(setup_database):
    """Test that empty keyword list doesn't crash."""
    SettingsService.set_setting('priority_high_keywords', [])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='URGENT',
        email_body='CRITICAL',
        due_date=None,
        ai_priority='medium'
    )
    assert priority == 'medium'


def test_empty_email_body(setup_database):
    """Test that empty email body doesn't crash."""
    SettingsService.set_setting('priority_high_keywords', ['URGENT'])

    priority = PriorityRuleEngine.apply_priority_rules(
        email_from='test@example.com',
        email_subject='Request',
        email_body='',
        due_date=None,
        ai_priority='medium'
    )
    assert priority == 'medium'
