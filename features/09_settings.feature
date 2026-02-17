Feature: Settings page
  As an administrator
  I want to configure priority rules, categories, and program settings
  So that the system matches our team's workflow

  # --- Page Display ---

  Scenario: View settings page
    Given the database is empty
    When I navigate to "/settings"
    Then the response status is 200
    And the page contains "Priority Rules"

  Scenario: Settings page shows default categories
    Given the database is empty
    When I navigate to "/settings"
    Then the response status is 200
    And the page contains "RFI"

  Scenario: Settings page shows program roster tab
    Given the database is empty
    When I navigate to "/settings"
    Then the response status is 200
    And the page contains "Program Roster"

  Scenario: Settings page shows categories tab
    Given the database is empty
    When I navigate to "/settings"
    Then the response status is 200
    And the page contains "Categories"

  Scenario: Settings page shows timezone field
    Given the database is empty
    When I navigate to "/settings"
    Then the response status is 200
    And the page contains "Timezone"

  Scenario: Settings page shows program name field
    Given the database is empty
    When I navigate to "/settings"
    Then the response status is 200
    And the page contains "Program Name"

  # --- Save Settings ---

  Scenario: Save priority settings
    Given the database is empty
    When I save settings with data
      | field                   | value             |
      | priority_default        | high              |
      | priority_days_threshold | 3                 |
      | priority_high_senders   | boss@example.com  |
      | priority_high_keywords  | urgent            |
      | confidence_threshold    | 0.7               |
      | timezone                | America/New_York  |
      | program_name            | TestProgram       |
    Then the response status is 303

  Scenario: Save settings with different timezone
    Given the database is empty
    When I save settings with data
      | field                   | value             |
      | priority_default        | medium            |
      | priority_days_threshold | 5                 |
      | priority_high_senders   |                   |
      | priority_high_keywords  |                   |
      | confidence_threshold    | 0.5               |
      | timezone                | America/Chicago   |
      | program_name            |                   |
    Then the response status is 303

  Scenario: Save settings with low default priority
    Given the database is empty
    When I save settings with data
      | field                   | value             |
      | priority_default        | low               |
      | priority_days_threshold | 10                |
      | priority_high_senders   |                   |
      | priority_high_keywords  |                   |
      | confidence_threshold    | 0.3               |
      | timezone                | America/Chicago   |
      | program_name            |                   |
    Then the response status is 303

  # --- Category Management ---

  Scenario: Add a new category
    Given the database is empty
    When I add a category named TestCategory
    Then the response status is 303

  Scenario: Delete an existing category
    Given the database is empty
    When I add a category named DeleteMe
    And I delete the category named DeleteMe
    Then the response status is 303

  Scenario: Adding duplicate category is handled
    Given the database is empty
    When I add a category named DupCategory
    And I add a category named DupCategory
    Then the response status is 303

  # --- Roster on Settings Page ---

  Scenario: Settings page shows roster members
    Given a roster member "Show" "OnSettings" with email "show@example.com" exists
    When I navigate to "/settings"
    Then the response status is 200
    And the page contains "show@example.com"
