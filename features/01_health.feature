Feature: Health and API stats endpoints
  As a system operator
  I want to verify the system is running
  So that I know the application is healthy

  Scenario: Health check on running system
    Given the database is empty
    When I navigate to "/health"
    Then the response status is 200
    And the page contains "healthy"

  Scenario: API stats returns zero counts on empty database
    Given the database is empty
    When I navigate to "/api/stats"
    Then the response status is 200
    And the JSON field total_emails equals 0
    And the JSON field total_actions equals 0
    And the JSON field unassigned_actions equals 0
    And the JSON field unassigned_high equals 0

  Scenario: API stats returns correct counts with data
    Given an unassigned "high" priority action exists with title "Test high action"
    And an unassigned "medium" priority action exists with title "Test medium action"
    When I navigate to "/api/stats"
    Then the response status is 200
    And the JSON field total_actions equals 2
    And the JSON field unassigned_actions equals 2
    And the JSON field unassigned_high equals 1
