Feature: Create new action manually
  As a team member
  I want to manually create action items from emails
  So that I can track things the AI might have missed

  Scenario: Create action form shows a category select dropdown
    Given an email exists with subject "Budget request email"
    When I navigate to the create action form for that email
    Then the response status is 200
    And the page contains "Create New Action"
    And the page contains "Select category"
    And the page contains "select"

  Scenario: Create action form shows the source email context
    Given an email exists with subject "Project status update"
    When I navigate to the create action form for that email
    Then the response status is 200
    And the page contains "Project status update"
    And the page contains "sender@example.com"

  Scenario: Create action with title only redirects to action detail
    Given an email exists with subject "Simple request"
    When I create a new action for that email with title "Simple action title"
    Then the response status is 303

  Scenario: Create action with all fields
    Given an email exists with subject "Complex request"
    When I create a new action with all fields
      | field       | value                   |
      | title       | Full action item        |
      | description | Detailed description    |
      | priority    | high                    |
      | due_date    | 2027-03-01              |
      | category    | RFI                     |
    Then the response status is 303

  Scenario: Create action form returns 404 for unknown email
    Given the database is empty
    When I navigate to "/emails/99999/actions/new"
    Then the response status is 404

  Scenario: Attempting to create action for unknown email via POST returns 404
    Given the database is empty
    When I submit a POST to /emails/99999/actions/new with data
      | field | value        |
      | title | Orphan title |
    Then the response status is 404
