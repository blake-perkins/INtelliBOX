Feature: Action detail page
  As a team member
  I want to view and edit action details
  So that I can manage individual action items

  # --- View Action Detail ---

  @smoke
  Scenario: View action detail page
    Given an unassigned "high" priority action exists with title "Review contract terms"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Review contract terms"
    And the page contains "Edit Action"

  Scenario: Action detail page shows source email
    Given an unassigned "medium" priority action exists with title "Reply to stakeholder"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "sender@example.com"

  Scenario: Action detail shows priority badge
    Given an unassigned "high" priority action exists with title "High badge test"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "HIGH"

  Scenario: Action detail shows assigned badge when assigned
    Given an action titled "Assigned badge test" is assigned to "alice@example.com"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "ASSIGNED"

  Scenario: Action detail shows completed badge when completed
    Given a completed action titled "Completed badge test" exists
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "COMPLETED"

  Scenario: Action detail shows overdue badge when overdue
    Given an overdue unassigned high priority action exists
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "OVERDUE"

  Scenario: Action detail shows category in sidebar
    Given an unassigned "medium" priority action exists with title "Cat sidebar test"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Category"
    And the page contains "RFI"

  Scenario: Action detail shows View Full Email link
    Given an unassigned "medium" priority action exists with title "Email link test"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "View Full Email"

  Scenario: Action detail shows related actions from same email
    Given an unassigned "high" priority action exists with title "Primary action"
    And an unassigned "low" priority action exists for the same email with title "Related action"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Related action"
    And the page contains "Other Actions from This Email"

  Scenario: View action detail for non-existent action
    Given the database is empty
    When I navigate to "/actions/99999"
    Then the response status is 404

  # --- Edit via Unified Form ---

  Scenario: Edit action fields via unified form
    Given an unassigned "medium" priority action exists with title "Full edit action"
    When I save a full edit form for the action
      | field       | value              |
      | title       | Fully edited title |
      | description | New description    |
      | priority    | high               |
      | due_date    | 2027-06-01         |
      | category    | RFI                |
    Then the response status is 303
    And the action priority is "high" in the database
    And the action title is "Fully edited title" in the database
    And the action category is "RFI" in the database

  Scenario: Edit action title only
    Given an unassigned "medium" priority action exists with title "Original title"
    When I save a full edit form for the action
      | field    | value         |
      | title    | Changed title |
      | priority | medium        |
    Then the response status is 303
    And the action title is "Changed title" in the database

  Scenario: Edit action to clear due date
    Given an unassigned "medium" priority action exists with title "Clear due date"
    When I save a full edit form for the action
      | field    | value          |
      | title    | Clear due date |
      | priority | medium         |
      | due_date |                |
    Then the response status is 303
    And the action has no due date in the database

  Scenario: Edit action to set due date
    Given an unassigned "medium" priority action exists with title "Set due date"
    When I save a full edit form for the action
      | field    | value         |
      | title    | Set due date  |
      | priority | medium        |
      | due_date | 2027-12-31    |
    Then the response status is 303

  Scenario: Edit action description
    Given an unassigned "medium" priority action exists with title "Edit desc"
    When I save a full edit form for the action
      | field       | value              |
      | title       | Edit desc          |
      | priority    | medium             |
      | description | Updated details    |
    Then the response status is 303

  Scenario: Edit action category
    Given an unassigned "medium" priority action exists with title "Edit category"
    When I save a full edit form for the action
      | field    | value         |
      | title    | Edit category |
      | priority | medium        |
      | category | deliverable   |
    Then the response status is 303
    And the action category is "deliverable" in the database

  # --- Edit + Assignment in One Submit ---

  Scenario: Edit action and assign in one submit
    Given an unassigned "medium" priority action exists with title "Assign and edit"
    And a roster member "Jane" "Doe" with email "jane@example.com" exists
    When I save a full edit form for the action
      | field       | value            |
      | title       | Assign and edit  |
      | priority    | high             |
      | assigned_to | Jane Doe         |
      | notes       | Please handle    |
    Then the response status is 303
    And the action assignment is saved in the database
    And the action priority is "high" in the database
    And the action is assigned to "Jane Doe" in the database

  Scenario: Edit action without changing assignment
    Given an action titled "Already assigned" is assigned to "existing@example.com"
    When I save a full edit form for the action
      | field       | value               |
      | title       | Updated title       |
      | priority    | low                 |
      | assigned_to | existing@example.com|
    Then the response status is 303
    And the action priority is "low" in the database
    And the action assignment is saved in the database

  Scenario: Reassign via edit form
    Given an action titled "Reassign via form" is assigned to "old@example.com"
    When I save a full edit form for the action
      | field       | value              |
      | title       | Reassign via form  |
      | priority    | medium             |
      | assigned_to | new@example.com    |
    Then the response status is 303
    And the action is assigned to "new@example.com" in the database

  # --- Unassign via Edit Form ---

  Scenario: Unassign via dropdown selects Unassigned
    Given an action titled "Unassign via dropdown" is assigned to "someone@example.com"
    When I save a full edit form for the action
      | field       | value                  |
      | title       | Unassign via dropdown  |
      | priority    | medium                 |
      | assigned_to |                        |
    Then the response status is 303
    And the action has no assignment in the database

  # --- Mark Complete / Reopen ---

  Scenario: Mark assigned action complete from detail page
    Given an action titled "Complete from detail" is assigned to "worker@example.com"
    When I change the action status to "completed"
    Then the response status is 303
    And the action is marked as "completed" in the database

  Scenario: Reopen a completed action from detail page
    Given a completed action titled "Reopen from detail" exists
    When I change the action status to "assigned"
    Then the response status is 303
    And the action is marked as "assigned" in the database

  # --- Delete ---

  Scenario: Delete an action
    Given an unassigned "low" priority action exists with title "Delete me"
    When I delete the action
    Then the response status is 303
    And the action no longer exists in the database
