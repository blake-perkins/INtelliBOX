"""Integration tests for AI clients with priority rules."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from emailtools.ai.mock_client import MockAIClient
from emailtools.models import Email, Base, Settings
from emailtools.settings_service import SettingsService
from emailtools import database


# Create a unique temporary database file for this test module
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_priority_integration.db', prefix='test_emailtools_')
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


# Patch the get_session function
database.get_session = override_get_session


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


@pytest.fixture
def mock_client():
    """Create a mock AI client for testing."""
    return MockAIClient()


@pytest.fixture
def sample_email():
    """Create a sample email for testing."""
    return Email(
        id=1,
        message_id='test-123@example.com',
        subject='Test RFI Request',
        from_address='customer@example.com',
        from_name='Test Customer',
        to_addresses='["team@company.com"]',
        received_date=datetime.utcnow(),
        body_text='We need this information by Friday. Can you provide the security audit report?',
        processed=False
    )


def test_priority_override_high_sender(setup_database, mock_client, sample_email):
    """Test that high-priority sender overrides AI priority."""
    SettingsService.set_setting('priority_high_senders', ['customer@example.com'])

    sample_email.from_address = 'customer@example.com'
    sample_email.subject = 'Regular request'
    sample_email.body_text = 'Can you help with this?'

    # Extract actions (AI would suggest low/medium)
    action_dicts, raw_response = mock_client.extract_actions(sample_email)
    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # All actions should be high priority due to sender rule
    for action in actions:
        assert action.priority == 'high'


def test_priority_override_keyword(setup_database, mock_client, sample_email):
    """Test that keyword in subject/body overrides AI priority."""
    SettingsService.set_setting('priority_high_keywords', ['URGENT', 'CRITICAL'])

    sample_email.subject = 'URGENT: Need response'
    sample_email.body_text = 'Please respond when you can.'

    # Extract actions
    action_dicts, raw_response = mock_client.extract_actions(sample_email)
    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # Actions should be high priority due to keyword
    for action in actions:
        assert action.priority == 'high'


def test_priority_override_due_date(setup_database, mock_client, sample_email):
    """Test that near due date overrides AI priority."""
    SettingsService.set_setting('priority_days_threshold', 5)

    # Email requesting something due in 2 days
    future_date = datetime.utcnow() + timedelta(days=2)
    sample_email.body_text = f'We need this by {future_date.strftime("%A")}.'  # Day of week

    # Extract actions
    action_dicts, raw_response = mock_client.extract_actions(sample_email)
    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # If any actions have due dates within threshold, they should be high priority
    for action in actions:
        if action.due_date and (action.due_date - datetime.utcnow()).days <= 5:
            assert action.priority == 'high'


def test_no_override_when_no_rules_match(setup_database, mock_client, sample_email):
    """Test that priority stays as AI suggested when no rules match."""
    SettingsService.set_setting('priority_high_senders', [])
    SettingsService.set_setting('priority_high_keywords', [])

    sample_email.subject = 'FYI: Status update'
    sample_email.body_text = 'Just wanted to let you know things are going well.'

    # Extract actions (should be no actions for FYI)
    action_dicts, raw_response = mock_client.extract_actions(sample_email)
    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # FYI emails typically have no actions
    assert len(actions) == 0


def test_multiple_actions_same_priority_rules(setup_database, mock_client, sample_email):
    """Test that priority rules apply to all actions from same email."""
    SettingsService.set_setting('priority_high_senders', ['vip@company.com'])

    sample_email.from_address = 'vip@company.com'
    sample_email.subject = 'Multiple requests'
    sample_email.body_text = '''
    I need help with three things:
    1. Update the documentation
    2. Fix the login bug
    3. Review the security audit
    '''

    # Extract actions
    action_dicts, raw_response = mock_client.extract_actions(sample_email)
    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # All actions should have high priority (same sender rule)
    assert len(actions) > 0
    for action in actions:
        assert action.priority == 'high'


def test_domain_match_priority(setup_database, mock_client, sample_email):
    """Test that domain-based sender matching works."""
    SettingsService.set_setting('priority_high_senders', ['@vip-client.com'])

    sample_email.from_address = 'anyone@vip-client.com'
    sample_email.subject = 'Request from VIP'
    sample_email.body_text = 'Can you provide this information?'

    # Extract actions
    action_dicts, raw_response = mock_client.extract_actions(sample_email)
    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # Actions should be high priority due to domain match
    for action in actions:
        assert action.priority == 'high'


def test_case_insensitive_keyword_matching(setup_database, mock_client, sample_email):
    """Test that keyword matching is case-insensitive."""
    SettingsService.set_setting('priority_high_keywords', ['urgent'])

    sample_email.subject = 'URGENT REQUEST'
    sample_email.body_text = 'Please help with this matter.'

    # Extract actions
    action_dicts, raw_response = mock_client.extract_actions(sample_email)
    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # Actions should be high priority (case-insensitive match)
    for action in actions:
        assert action.priority == 'high'


def test_default_priority_applied(setup_database, mock_client, sample_email):
    """Test that default priority is used when no rules match and AI doesn't specify."""
    SettingsService.set_setting('priority_default', 'low')
    SettingsService.set_setting('priority_high_senders', [])
    SettingsService.set_setting('priority_high_keywords', [])

    sample_email.subject = 'Simple request'
    sample_email.body_text = 'Can you review this document when you have time?'

    # Extract actions
    action_dicts, raw_response = mock_client.extract_actions(sample_email)

    # Modify action_dicts to remove priority (simulate AI not specifying)
    for action_dict in action_dicts:
        action_dict.pop('priority', None)

    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # Actions should have default priority
    for action in actions:
        assert action.priority == 'low'


def test_rfi_detection_with_priority_override(setup_database, mock_client, sample_email):
    """Test RFI detection combined with priority override."""
    SettingsService.set_setting('priority_high_keywords', ['RFI'])

    sample_email.subject = 'RFI: Security Information'
    sample_email.body_text = 'Please provide security audit details by end of week.'

    # Extract actions
    action_dicts, raw_response = mock_client.extract_actions(sample_email)
    actions = mock_client.create_action_objects(sample_email, action_dicts, raw_response)

    # Should detect RFI and set high priority
    assert len(actions) > 0
    for action in actions:
        assert action.priority == 'high'
        assert 'RFI' in action.category or 'RFI' in action.title


def test_priority_settings_change_affects_new_emails(setup_database, mock_client):
    """Test that changing settings affects subsequent email processing."""
    # First email - no high priority rules
    SettingsService.set_setting('priority_high_senders', [])

    email1 = Email(
        id=1, message_id='test-1@example.com',
        subject='Request', from_address='customer@example.com',
        from_name='Customer', to_addresses='["team@company.com"]',
        received_date=datetime.utcnow(),
        body_text='Can you help?', processed=False
    )

    action_dicts, raw_response = mock_client.extract_actions(email1)
    actions1 = mock_client.create_action_objects(email1, action_dicts, raw_response)

    # Change settings to make this sender high priority
    SettingsService.set_setting('priority_high_senders', ['customer@example.com'])

    # Second email from same sender
    email2 = Email(
        id=2, message_id='test-2@example.com',
        subject='Another request', from_address='customer@example.com',
        from_name='Customer', to_addresses='["team@company.com"]',
        received_date=datetime.utcnow(),
        body_text='Need more help', processed=False
    )

    action_dicts, raw_response = mock_client.extract_actions(email2)
    actions2 = mock_client.create_action_objects(email2, action_dicts, raw_response)

    # Second email's actions should be high priority
    for action in actions2:
        assert action.priority == 'high'
