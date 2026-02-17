Feature: Actions list page
  As a team member
  I want to view and filter the list of all actions
  So that I can find the actions I need to manage

  # --- Basic Page Load ---

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

  Scenario: Actions list shows action count
    Given an unassigned "high" priority action exists with title "Count me"
    When I navigate to "/actions"
    Then the response status is 200
    And the page contains "1 action"

  # --- Priority Filters ---

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

  # --- Assignment Status Filters ---

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

  Scenario: Filter to show only completed actions via completed param
    Given a completed action titled "Finished task" exists
    And an unassigned "high" priority action exists with title "Open task"
    When I navigate to "/actions?completed=true"
    Then the response status is 200
    And the page contains "Finished task"
    And the page does not contain "Open task"

  Scenario: Filter to show only completed actions via assigned=completed
    Given a completed action titled "Done task" exists
    And an unassigned "high" priority action exists with title "Pending task"
    When I navigate to "/actions?assigned=completed"
    Then the response status is 200
    And the page contains "Done task"
    And the page does not contain "Pending task"

  # --- Search Filter ---

  Scenario: Search actions by title
    Given an unassigned "high" priority action exists with title "Budget review needed"
    And an unassigned "medium" priority action exists with title "Meeting notes"
    When I navigate to "/actions?search=Budget"
    Then the response status is 200
    And the page contains "Budget review needed"
    And the page does not contain "Meeting notes"

  Scenario: Search actions with no results
    Given an unassigned "high" priority action exists with title "Something specific"
    When I navigate to "/actions?search=nonexistent"
    Then the response status is 200
    And the page contains "No actions found"

  # --- Overdue Filter ---

  Scenario: Filter actions by overdue
    Given an overdue unassigned high priority action exists
    And an unassigned "medium" priority action exists with title "Not overdue"
    When I navigate to "/actions?overdue=true"
    Then the response status is 200
    And the page contains "Overdue action item"
    And the page does not contain "Not overdue"

  # --- Combined Filters ---

  Scenario: Combine priority and assignment filters
    Given an unassigned "high" priority action exists with title "Unassigned high"
    And an action titled "Assigned high" is assigned to "bob@example.com"
    When I navigate to "/actions?priority=high&assigned=false"
    Then the response status is 200
    And the page contains "Unassigned high"

  # --- Assignee Filter ---

  Scenario: Filter actions by specific assignee
    Given an action titled "Bob task" is assigned to "bob@example.com"
    And an action titled "Alice task" is assigned to "alice@example.com"
    When I navigate to "/actions?assignee=bob@example.com"
    Then the response status is 200
    And the page contains "Bob task"
    And the page does not contain "Alice task"

  # --- Pagination ---

  Scenario: Paginate actions list
    Given an unassigned "medium" priority action exists with title "Paginated task"
    When I navigate to "/actions?page=1"
    Then the response status is 200

  Scenario: Invalid page number returns error
    Given the database is empty
    When I navigate to "/actions?page=0"
    Then the response status is 422

  # --- Quick Assign from List ---

  Scenario: Quick-assign action from actions list
    Given an unassigned "high" priority action exists with title "Assign from list"
    And a roster member "Bob" "Jones" with email "bob@example.com" exists
    When I assign the action to "bob@example.com"
    Then the response status is 303
    And the action assignment is saved in the database

  # --- Sections ---

  Scenario: Actions list shows open actions section
    Given an unassigned "high" priority action exists with title "Open item"
    When I navigate to "/actions"
    Then the response status is 200
    And the page contains "Open Actions"

  Scenario: Actions list shows completed section when completed actions exist
    Given a completed action titled "Done item" exists
    When I navigate to "/actions"
    Then the response status is 200
    And the page contains "Completed"

  # --- Clear Filters ---

  Scenario: Actions list shows clear filters link when filters active
    Given an unassigned "high" priority action exists with title "Filtered item"
    When I navigate to "/actions?priority=high"
    Then the response status is 200
    And the page contains "Clear All"

  Scenario: Actions list does not show clear filters when no filters active
    Given an unassigned "high" priority action exists with title "Unfiltered item"
    When I navigate to "/actions"
    Then the response status is 200
    And the page does not contain "Clear All"
