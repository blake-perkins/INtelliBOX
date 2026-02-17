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

  Scenario: Edit action title
    Given an unassigned "medium" priority action exists with title "Original title"
    When I edit the action title to "Updated title"
    Then the response status is 303

  Scenario: Edit action description
    Given an unassigned "medium" priority action exists with title "Action to describe"
    When I edit the action description to "Updated description text"
    Then the response status is 303

  Scenario: Edit action priority
    Given an unassigned "low" priority action exists with title "Low priority action"
    When I edit the action title to "Low priority action"
    And I change the action priority to "high"
    Then the response status is 303
    And the action priority is "high" in the database

  Scenario: Edit action due date
    Given an unassigned "medium" priority action exists with title "Action with due date"
    When I edit the action due date to "2027-01-15"
    Then the response status is 303

  Scenario: Edit action category
    Given an unassigned "medium" priority action exists with title "Categorize me"
    When I edit the action category to "RFI"
    Then the response status is 303

  Scenario: Save full edit form for action
    Given an unassigned "medium" priority action exists with title "Full edit action"
    When I save a full edit form for the action
      | field       | value              |
      | title       | Fully edited title |
      | description | New description    |
      | priority    | high               |
      | due_date    | 2027-06-01         |
      | category    | RFI                |
    Then the response status is 303

  Scenario: Delete an action
    Given an unassigned "low" priority action exists with title "Delete me"
    When I delete the action
    Then the response status is 303
