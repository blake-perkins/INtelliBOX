Feature: Dashboard
  As a team member
  I want to see unassigned actions grouped by priority on the dashboard
  So that I can quickly understand what needs attention

  # --- Page Load Variations ---

  Scenario: Empty dashboard loads without errors
    Given the database is empty
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Dashboard"

  Scenario: Dashboard shows "All Clear" when no overdue or high priority actions
    Given an unassigned "medium" priority action exists with title "Medium only"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "All Clear"

  Scenario: Dashboard hides "All Clear" when high priority actions exist
    Given an unassigned "high" priority action exists with title "High alert"
    When I navigate to "/"
    Then the response status is 200
    And the page does not contain "All Clear"

  Scenario: Dashboard hides "All Clear" when overdue actions exist
    Given an overdue unassigned high priority action exists
    When I navigate to "/"
    Then the response status is 200
    And the page does not contain "All Clear"

  # --- Priority Sections ---

  Scenario: Dashboard shows high priority unassigned action
    Given an unassigned "high" priority action exists with title "Critical RFI response"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Critical RFI response"
    And the page contains "High Priority"

  Scenario: Dashboard shows medium priority unassigned action
    Given an unassigned "medium" priority action exists with title "Medium priority task"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Medium priority task"
    And the page contains "Medium Priority"

  Scenario: Dashboard shows low priority unassigned action
    Given an unassigned "low" priority action exists with title "Low priority task"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Low priority task"
    And the page contains "Low Priority"

  Scenario: Dashboard shows medium and low priority side by side
    Given an unassigned "medium" priority action exists with title "Medium side item"
    And an unassigned "low" priority action exists with title "Low side item"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Medium side item"
    And the page contains "Low side item"
    And the page contains "Medium Priority"
    And the page contains "Low Priority"

  Scenario: Dashboard shows overdue action
    Given an overdue unassigned high priority action exists
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Overdue action item"
    And the page contains "Overdue"

  Scenario: Dashboard loads correctly with only assigned actions
    Given an action titled "Already taken" is assigned to "bob@example.com"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "All Clear"

  Scenario: Dashboard loads correctly with only completed actions
    Given a completed action titled "Already done" exists
    When I navigate to "/"
    Then the response status is 200
    And the page contains "All Clear"

  # --- Recent Activity ---

  Scenario: Dashboard shows recent assignments
    Given an action titled "Recently assigned" is assigned to "alice@example.com"
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Recently assigned"
    And the page contains "alice@example.com"

  Scenario: Dashboard shows recent completions
    Given a completed action titled "Recently completed" exists
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Recently completed"

  # --- Quick Actions (Priority Change — all 6 transitions) ---

  Scenario: Change priority of an action via edit form
    Given an unassigned "high" priority action exists with title "Reprioritize this"
    When I save a full edit form for the action
      | field    | value             |
      | title    | Reprioritize this |
      | priority | low               |
    Then the response status is 303
    And the action priority is "low" in the database

  Scenario: Quick-change priority from medium to high
    Given an unassigned "medium" priority action exists with title "Promote me"
    When I quick-change the action priority to "high"
    Then the response status is 303
    And the action priority is "high" in the database

  Scenario: Quick-change priority from high to low
    Given an unassigned "high" priority action exists with title "Demote me"
    When I quick-change the action priority to "low"
    Then the response status is 303
    And the action priority is "low" in the database

  Scenario: Quick-change priority from low to medium
    Given an unassigned "low" priority action exists with title "Bump me up"
    When I quick-change the action priority to "medium"
    Then the response status is 303
    And the action priority is "medium" in the database

  Scenario: Quick-change priority from high to medium
    Given an unassigned "high" priority action exists with title "Downgrade to medium"
    When I quick-change the action priority to "medium"
    Then the response status is 303
    And the action priority is "medium" in the database

  Scenario: Quick-change priority from medium to low
    Given an unassigned "medium" priority action exists with title "Downgrade to low"
    When I quick-change the action priority to "low"
    Then the response status is 303
    And the action priority is "low" in the database

  Scenario: Quick-change priority from low to high
    Given an unassigned "low" priority action exists with title "Escalate to high"
    When I quick-change the action priority to "high"
    Then the response status is 303
    And the action priority is "high" in the database

  Scenario: Quick-change priority with invalid value is ignored
    Given an unassigned "high" priority action exists with title "Leave me alone"
    When I quick-change the action priority to "critical"
    Then the response status is 303
    And the action priority is "high" in the database

  # --- Quick Actions (Assignment) ---

  Scenario: Quick-assign an action
    Given an unassigned "high" priority action exists with title "Quick assign me"
    And a roster member "Alice" "Smith" with email "alice@example.com" exists
    When I assign the action to "alice@example.com"
    Then the response status is 303
    And the action assignment is saved in the database

  Scenario: Quick-unassign a previously assigned action
    Given an action titled "Unassign from dashboard" is assigned to "bob@example.com"
    When I quick-unassign the action
    Then the response status is 303
    And the action has no assignment in the database

  # --- Dashboard Roster Dropdown ---

  Scenario: Dashboard shows roster members in assign dropdown
    Given an unassigned "high" priority action exists with title "Show dropdown"
    And a roster member "Test" "Member" with email "test@example.com" exists
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Member, Test"
