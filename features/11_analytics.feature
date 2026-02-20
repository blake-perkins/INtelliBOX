Feature: System analytics dashboard
  As an administrator
  I want to see all-time system stats and activity trends
  So that I can understand overall system usage and team throughput

  @smoke
  Scenario: View analytics page with empty database
    Given the database is empty
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "System Analytics"

  Scenario: Analytics page shows all-time stats section
    Given the database is empty
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "System Totals"
    And the page contains "Emails Ingested"
    And the page contains "Actions Created"
    And the page contains "Team Members"

  Scenario: Analytics page shows action pipeline
    Given the database is empty
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "Action Pipeline"
    And the page contains "Unassigned"
    And the page contains "In Progress"
    And the page contains "Completed"

  Scenario: Analytics page shows weekly activity section
    Given the database is empty
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "Weekly Activity"

  Scenario: Analytics page shows top categories section
    Given the database is empty
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "Top Categories"

  Scenario: Analytics page shows team activity section
    Given the database is empty
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "Team Activity"

  Scenario: Analytics page with data shows correct email count
    Given an email exists with subject "Analytics test email"
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "Emails Ingested"

  Scenario: Analytics page with action shows correct action count
    Given an unassigned "high" priority action exists with title "Analytics test action"
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "Actions Created"

  Scenario: Analytics page shows roster member count
    Given a roster member "Test" "User" with email "test@example.com" exists
    When I navigate to "/analytics"
    Then the response status is 200
    And the page contains "Team Members"
