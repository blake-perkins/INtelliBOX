Feature: Actions list page
  As a team member
  I want to view and filter the list of all actions
  So that I can find the actions I need to manage

  Scenario: View actions list page with no data
    Given the database is empty
    When I navigate to "/actions"
    Then the response status is 200
    And the page contains "No actions found"

  Scenario: View all actions with data
    Given an unassigned "high" priority action exists with title "Budget inquiry response"
    And an unassigned "medium" priority action exists with title "Meeting follow-up"
    When I navigate to "/actions"
    Then the response status is 200
    And the page contains "Budget inquiry response"
    And the page contains "Meeting follow-up"

  Scenario: Filter actions by high priority
    Given an unassigned "high" priority action exists with title "High priority task"
    And an unassigned "low" priority action exists with title "Low priority task"
    When I navigate to "/actions?priority=high"
    Then the response status is 200
    And the page contains "High priority task"
    And the page does not contain "Low priority task"

  Scenario: Filter actions by medium priority
    Given an unassigned "medium" priority action exists with title "Medium task"
    And an unassigned "high" priority action exists with title "High task"
    When I navigate to "/actions?priority=medium"
    Then the response status is 200
    And the page contains "Medium task"
    And the page does not contain "High task"

  Scenario: Filter actions by low priority
    Given an unassigned "low" priority action exists with title "Low task"
    And an unassigned "high" priority action exists with title "High task"
    When I navigate to "/actions?priority=low"
    Then the response status is 200
    And the page contains "Low task"
    And the page does not contain "High task"

  Scenario: Filter to show only unassigned actions
    Given an unassigned "high" priority action exists with title "Unassigned task"
    And an action titled "Assigned task" is assigned to "bob@example.com"
    When I navigate to "/actions?assigned=false"
    Then the response status is 200
    And the page contains "Unassigned task"
    And the page does not contain "Assigned task"

  Scenario: Filter to show only assigned actions
    Given an unassigned "high" priority action exists with title "Unassigned task"
    And an action titled "Assigned task" is assigned to "bob@example.com"
    When I navigate to "/actions?assigned=true"
    Then the response status is 200
    And the page contains "Assigned task"
    And the page does not contain "Unassigned task"

  Scenario: Paginate actions list
    Given an unassigned "medium" priority action exists with title "Paginated task"
    When I navigate to "/actions?page=1"
    Then the response status is 200

  Scenario: Invalid page number returns error
    Given the database is empty
    When I navigate to "/actions?page=0"
    Then the response status is 422

  Scenario: Quick-assign action from actions list
    Given an unassigned "high" priority action exists with title "Assign from list"
    And a roster member "Bob" "Jones" with email "bob@example.com" exists
    When I assign the action to "bob@example.com"
    Then the response status is 303
    And the action assignment is saved in the database
