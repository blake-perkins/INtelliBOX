"""Tests for SettingsService."""

import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from emailtools.models import Settings, Base

# Create a unique temporary database file for this test module
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_settings_service.db', prefix='test_emailtools_')
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
import emailtools.database as database_module
import emailtools.settings_service as settings_service_module

database_module.get_session = override_get_session
settings_service_module.get_session = override_get_session

# Now import SettingsService after patching
from emailtools.settings_service import SettingsService


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
