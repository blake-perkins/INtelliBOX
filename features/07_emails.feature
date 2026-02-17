Feature: Email list and email detail
  As a team member
  I want to view emails and navigate to their associated actions
  So that I can understand the full context of each action item

  # --- Email List ---

  Scenario: View email list page with no emails
    Given the database is empty
    When I navigate to "/emails"
    Then the response status is 200
    And the page contains "No emails found"

  Scenario: View email list with data
    Given an email exists with subject "Important RFI from stakeholder"
    When I navigate to "/emails"
    Then the response status is 200
    And the page contains "Important RFI from stakeholder"

  Scenario: Email list shows sender name
    Given an email exists with subject "Sender address test"
    When I navigate to "/emails"
    Then the response status is 200
    And the page contains "sender"

  # --- Email Search ---

  Scenario: Search emails by subject
    Given an email exists with subject "Quarterly budget report"
    And an email exists with subject "Team lunch planning"
    When I navigate to "/emails?search=budget"
    Then the response status is 200
    And the page contains "Quarterly budget report"
    And the page does not contain "Team lunch planning"

  Scenario: Search emails with no results
    Given an email exists with subject "Existing email"
    When I navigate to "/emails?search=nonexistent"
    Then the response status is 200
    And the page contains "No emails found"

  # --- Processed Filter ---

  Scenario: Filter to show only processed emails
    Given an email exists with subject "Processed email"
    And an unprocessed email exists with subject "Unprocessed email"
    When I navigate to "/emails?processed=true"
    Then the response status is 200
    And the page contains "Processed email"
    And the page does not contain "Unprocessed email"

  Scenario: Filter to show only unprocessed emails
    Given an email exists with subject "Processed email two"
    And an unprocessed email exists with subject "Unprocessed email two"
    When I navigate to "/emails?processed=false"
    Then the response status is 200
    And the page contains "Unprocessed email two"
    And the page does not contain "Processed email two"

  # --- Email Detail ---

  Scenario: View email detail page
    Given an email exists with subject "Detailed email subject"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "Detailed email subject"
    And the page contains "sender@example.com"

  Scenario: Email detail page shows email body
    Given an email exists with subject "Body content test"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "Body of email: Body content test"

  Scenario: Email detail page shows PROCESSED badge for processed emails
    Given an email exists with subject "Processed badge test"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "PROCESSED"

  Scenario: Email detail page shows PENDING badge for unprocessed emails
    Given an unprocessed email exists with subject "Pending badge test"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "PENDING"

  Scenario: Email detail page shows related actions
    Given an unassigned "high" priority action exists with title "Action from this email"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "Action from this email"

  Scenario: Email detail page shows action count
    Given an unassigned "high" priority action exists with title "Counted action"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "1 ACTION"

  Scenario: Email detail shows Create Action button
    Given an email exists with subject "Email needing manual action"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "Create Action"

  Scenario: Email detail shows no actions message when none exist
    Given an email exists with subject "No actions email"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "No actions extracted"

  Scenario: View email detail for non-existent email
    Given the database is empty
    When I navigate to "/emails/99999"
    Then the response status is 404

  # --- Pagination ---

  Scenario: Paginate emails list
    Given an email exists with subject "Paged email"
    When I navigate to "/emails?page=1"
    Then the response status is 200

  Scenario: Invalid page number for emails returns error
    Given the database is empty
    When I navigate to "/emails?page=0"
    Then the response status is 422
