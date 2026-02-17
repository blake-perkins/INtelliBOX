Feature: Dashboard
  As a team member
  I want to see unassigned actions grouped by priority on the dashboard
  So that I can quickly understand what needs attention

  Scenario: Empty dashboard loads without errors
    Given the database is empty
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Dashboard"

  Scenario: Dashboard shows high priority unassigned action
    Given an unassigned "high" priority action exists with title "Critical RFI response"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Critical RFI response"

  Scenario: Dashboard shows medium priority unassigned action
    Given an unassigned "medium" priority action exists with title "Medium priority task"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Medium priority task"

  Scenario: Dashboard shows low priority unassigned action
    Given an unassigned "low" priority action exists with title "Low priority task"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Low priority task"

  Scenario: Dashboard shows overdue action
    Given an overdue unassigned high priority action exists
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Overdue action item"

  Scenario: Change priority of an action
    Given an unassigned "high" priority action exists with title "Reprioritize this"
    When I change the action priority to "low"
    Then the response status is 303
    And the action priority is "low" in the database

  Scenario: Quick-assign an action
    Given an unassigned "high" priority action exists with title "Quick assign me"
    And a roster member "Alice" "Smith" with email "alice@example.com" exists
    When I assign the action to "alice@example.com"
    Then the response status is 303
    And the action assignment is saved in the database
