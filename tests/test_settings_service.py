"""Tests for SettingsService."""

import os
import tempfile
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from intellibox.models import Base, Settings

# Create a unique temporary database file for this test module
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_settings_service.db', prefix='test_intellibox_')
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


# Patch get_session in both database module and settings_service module
import intellibox.database as database_module
import intellibox.settings_service as settings_service_module

database_module.get_session = override_get_session
settings_service_module.get_session = override_get_session

# Now import SettingsService after patching
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
    """Clear data before each test to ensure isolation."""
    # Clear any existing data to ensure test isolation
    with override_get_session() as session:
        session.query(Settings).delete()
        session.commit()
        session.flush()

    # Ensure all connections see the cleared state
    test_engine.dispose()

    yield

    # Clean up after test
    with override_get_session() as session:
        session.query(Settings).delete()
        session.commit()
        session.flush()

    # Ensure clean state for next test
    test_engine.dispose()


def test_set_and_get_string_setting(setup_database):
    """Test setting and getting a string value."""
    SettingsService.set_setting('test_key', 'test_value', 'Test description')

    value = SettingsService.get_setting('test_key')
    assert value == 'test_value'


def test_set_and_get_int_setting(setup_database):
    """Test setting and getting an integer value."""
    SettingsService.set_setting('priority_days_threshold', 7)

    value = SettingsService.get_setting('priority_days_threshold')
    assert value == 7
    assert isinstance(value, int)


def test_set_and_get_list_setting(setup_database):
    """Test setting and getting a list value."""
    test_list = ['item1@example.com', '@company.com', 'user@test.com']
    SettingsService.set_setting('priority_high_senders', test_list)

    value = SettingsService.get_setting('priority_high_senders')
    assert value == test_list
    assert isinstance(value, list)


def test_get_nonexistent_setting_returns_default(setup_database):
    """Test that getting a nonexistent setting returns the default value."""
    value = SettingsService.get_setting('nonexistent_key', 'default_value')
    assert value == 'default_value'


def test_update_existing_setting(setup_database):
    """Test updating an existing setting."""
    SettingsService.set_setting('test_key', 'initial_value')
    SettingsService.set_setting('test_key', 'updated_value')

    value = SettingsService.get_setting('test_key')
    assert value == 'updated_value'


def test_get_all_settings(setup_database):
    """Test getting all settings as a dictionary."""
    SettingsService.set_setting('key1', 'value1')
    SettingsService.set_setting('key2', 42)
    SettingsService.set_setting('key3', ['a', 'b', 'c'])

    all_settings = SettingsService.get_all_settings()

    assert all_settings['key1'] == 'value1'
    assert all_settings['key2'] == 42
    assert all_settings['key3'] == ['a', 'b', 'c']


def test_get_priority_config(setup_database):
    """Test getting priority configuration settings."""
    # Set priority settings
    SettingsService.set_setting('priority_days_threshold', 5)
    SettingsService.set_setting('priority_high_senders', ['test@example.com'])
    SettingsService.set_setting('priority_high_keywords', ['URGENT', 'CRITICAL'])
    SettingsService.set_setting('priority_default', 'medium')

    config = SettingsService.get_priority_config()

    assert config['days_threshold'] == 5
    assert config['high_senders'] == ['test@example.com']
    assert config['high_keywords'] == ['URGENT', 'CRITICAL']
    assert config['default_priority'] == 'medium'


def test_priority_config_with_defaults(setup_database):
    """Test that priority config returns defaults when settings don't exist."""
    # Clear any existing settings first to ensure clean state
    with override_get_session() as session:
        session.query(Settings).delete()
        session.commit()

    config = SettingsService.get_priority_config()

    assert config['days_threshold'] == 5  # default
    assert config['high_senders'] == []  # default
    assert config['high_keywords'] == []  # default
    assert config['default_priority'] == 'medium'  # default


def test_setting_description_stored(setup_database):
    """Test that setting descriptions are stored correctly."""
    test_key = 'test_key_desc_unique'
    SettingsService.set_setting(test_key, 'test_value', 'This is a test description')

    # Query to verify value
    value = SettingsService.get_setting(test_key)
    assert value == 'test_value'

    # Verify description exists in database (query right after setting)
    with override_get_session() as session:
        setting = session.query(Settings).filter_by(key=test_key).first()
        if setting is None:
            # If not found, print all settings for debugging
            all_settings = session.query(Settings).all()
            print(f"Could not find setting '{test_key}'. All settings: {[s.key for s in all_settings]}")
        assert setting is not None, f"Setting '{test_key}' not found in database"
        assert setting.description == 'This is a test description'


def test_setting_updated_at_changes(setup_database):
    """Test that setting value can be updated."""
    SettingsService.set_setting('test_key_update', 'initial')

    # Verify initial value
    value1 = SettingsService.get_setting('test_key_update')
    assert value1 == 'initial'

    # Update the value
    SettingsService.set_setting('test_key_update', 'updated')

    # Verify updated value
    value2 = SettingsService.get_setting('test_key_update')
    assert value2 == 'updated'


# ── AI config & category parsing ────────────────────────────────────────────

def test_ai_config_defaults(setup_database):
    """get_ai_config returns expected defaults when nothing is saved."""
    config = SettingsService.get_ai_config()
    assert config['confidence_threshold'] == 0.5
    assert config['categories'] == SettingsService.DEFAULT_CATEGORIES


def test_ai_config_roundtrip(setup_database):
    """Saving and loading ai_config values preserves them exactly."""
    SettingsService.set_setting('ai_confidence_threshold', 0.75)
    custom = [{"name": "custom", "description": "A custom category"}]
    SettingsService.set_setting('ai_categories', custom)

    config = SettingsService.get_ai_config()
    assert config['confidence_threshold'] == 0.75
    assert config['categories'] == custom


def test_parse_categories_normal(setup_database):
    """Standard name: description lines are parsed correctly."""
    text = "RFI: Request for Information\ndata_call: Data request"
    result = SettingsService.parse_categories_text(text)
    assert result == [
        {"name": "RFI", "description": "Request for Information"},
        {"name": "data_call", "description": "Data request"},
    ]


def test_parse_categories_colon_in_description(setup_database):
    """A colon inside the description is preserved (only first colon splits)."""
    text = "RFI: See docs: section 3"
    result = SettingsService.parse_categories_text(text)
    assert result == [{"name": "RFI", "description": "See docs: section 3"}]


def test_parse_categories_blank_lines_ignored(setup_database):
    """Blank and whitespace-only lines are silently skipped."""
    text = "\n  \nRFI: Request for Information\n\ndata_call: Data request\n"
    result = SettingsService.parse_categories_text(text)
    assert len(result) == 2
    assert result[0]["name"] == "RFI"
    assert result[1]["name"] == "data_call"


def test_parse_categories_no_colon_skipped(setup_database):
    """Lines without a colon are ignored, valid lines still parsed."""
    text = "this line has no colon\nRFI: Request for Information"
    result = SettingsService.parse_categories_text(text)
    assert result == [{"name": "RFI", "description": "Request for Information"}]


def test_parse_categories_empty_name_skipped(setup_database):
    """A line starting with a colon (empty name) is skipped."""
    text = ": some description\nRFI: Request for Information"
    result = SettingsService.parse_categories_text(text)
    assert result == [{"name": "RFI", "description": "Request for Information"}]


def test_parse_categories_empty_description_skipped(setup_database):
    """A line with a name but empty description is skipped."""
    text = "RFI:\ndata_call: Data request"
    result = SettingsService.parse_categories_text(text)
    assert result == [{"name": "data_call", "description": "Data request"}]


def test_parse_categories_empty_input_returns_defaults(setup_database):
    """An empty string falls back to DEFAULT_CATEGORIES."""
    result = SettingsService.parse_categories_text("")
    assert result == SettingsService.DEFAULT_CATEGORIES


def test_parse_categories_all_invalid_returns_defaults(setup_database):
    """All-invalid lines (no colons) fall back to DEFAULT_CATEGORIES."""
    text = "no colon here\nalso no colon"
    result = SettingsService.parse_categories_text(text)
    assert result == SettingsService.DEFAULT_CATEGORIES


def test_parse_categories_whitespace_trimmed(setup_database):
    """Leading/trailing whitespace on name and description is stripped."""
    text = "  RFI  :   Request for Information   "
    result = SettingsService.parse_categories_text(text)
    assert result == [{"name": "RFI", "description": "Request for Information"}]


def test_format_categories_for_prompt(setup_database):
    """format_categories_for_prompt produces bullet lines for the AI prompt."""
    cats = [
        {"name": "RFI", "description": "Request for Information"},
        {"name": "other", "description": "Everything else"},
    ]
    prompt_text = SettingsService.format_categories_for_prompt(cats)
    assert '   - "RFI": Request for Information' in prompt_text
    assert '   - "other": Everything else' in prompt_text


# ── Insights prompt ─────────────────────────────────────────────────────────

def test_get_insights_prompt_default(setup_database):
    """get_insights_prompt returns hardcoded default when no custom prompt saved."""
    from intellibox.ai.prompts import REPORT_INSIGHTS_PROMPT
    prompt = SettingsService.get_insights_prompt()
    assert prompt == REPORT_INSIGHTS_PROMPT


def test_get_insights_prompt_custom(setup_database):
    """get_insights_prompt returns the custom prompt when one is saved."""
    custom = "Analyze {action_details} and summarize."
    SettingsService.set_setting("insights_prompt", custom)
    prompt = SettingsService.get_insights_prompt()
    assert prompt == custom


def test_get_insights_prompt_roundtrip(setup_database):
    """Saving and loading a custom insights prompt preserves it exactly."""
    custom = "Prompt with {total_actions} and {days} placeholders and special chars: <>&\""
    SettingsService.set_setting("insights_prompt", custom)
    assert SettingsService.get_insights_prompt() == custom


def test_get_insights_prompt_after_delete(setup_database):
    """After delete_setting, get_insights_prompt falls back to the default."""
    from intellibox.ai.prompts import REPORT_INSIGHTS_PROMPT
    SettingsService.set_setting("insights_prompt", "custom prompt")
    SettingsService.delete_setting("insights_prompt")
    prompt = SettingsService.get_insights_prompt()
    assert prompt == REPORT_INSIGHTS_PROMPT


# ── delete_setting ──────────────────────────────────────────────────────────

def test_delete_setting_removes_row(setup_database):
    """delete_setting removes the row so get_setting returns default."""
    SettingsService.set_setting("ephemeral_key", "value")
    assert SettingsService.get_setting("ephemeral_key") == "value"
    SettingsService.delete_setting("ephemeral_key")
    assert SettingsService.get_setting("ephemeral_key", "gone") == "gone"


def test_delete_setting_nonexistent_is_noop(setup_database):
    """Deleting a key that doesn't exist doesn't raise."""
    SettingsService.delete_setting("never_existed")  # should not raise


def test_delete_setting_does_not_affect_others(setup_database):
    """Deleting one key leaves other keys intact."""
    SettingsService.set_setting("keep_me", "alive")
    SettingsService.set_setting("delete_me", "bye")
    SettingsService.delete_setting("delete_me")
    assert SettingsService.get_setting("keep_me") == "alive"
    assert SettingsService.get_setting("delete_me", None) is None
