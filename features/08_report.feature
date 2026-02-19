Feature: Insights / Report page
  As a manager
  I want to view a summary report of email activity and unassigned actions
  So that I can stay on top of team workload

  Scenario: View report page with no data
    Given the database is empty
    When I navigate to "/insights"
    Then the response status is 200
    And the page contains "Insights"

  Scenario: View report page with actions shows generate button
    Given an unassigned "high" priority action exists with title "Pending action"
    When I navigate to "/insights"
    Then the response status is 200
    And the page contains "Insights"

  Scenario: View report page does not crash on empty database
    Given the database is empty
    When I navigate to "/insights"
    Then the response status is 200
    And the page does not contain "Internal Server Error"

  Scenario: Report page shows Generate button when no insights cached
    Given the database is empty
    When I navigate to "/insights"
    Then the response status is 200
    And the page contains "Generate Insights"

  Scenario: Report generate API endpoint returns job ID
    Given the database is empty
    When I POST to "/api/insights/generate"
    Then the response status is 200
