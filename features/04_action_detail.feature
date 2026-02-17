Feature: Action detail page
  As a team member
  I want to view and edit action details
  So that I can manage individual action items

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

  Scenario: View action detail for non-existent action
    Given the database is empty
    When I navigate to "/actions/99999"
    Then the response status is 404

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

  Scenario: Edit action and assign in one submit
    Given an unassigned "medium" priority action exists with title "Assign and edit"
    And a roster member "Jane" "Doe" with email "jane@example.com" exists
    When I save a full edit form for the action
      | field       | value            |
      | title       | Assign and edit  |
      | priority    | high             |
      | assigned_to | Doe, Jane        |
      | notes       | Please handle    |
    Then the response status is 303
    And the action assignment is saved in the database
    And the action priority is "high" in the database

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

  Scenario: Unassign via dropdown selects Unassigned
    Given an action titled "Unassign via dropdown" is assigned to "someone@example.com"
    When I save a full edit form for the action
      | field       | value                  |
      | title       | Unassign via dropdown  |
      | priority    | medium                 |
      | assigned_to |                        |
    Then the response status is 303
    And the action has no assignment in the database

  Scenario: Delete an action
    Given an unassigned "low" priority action exists with title "Delete me"
    When I delete the action
    Then the response status is 303
