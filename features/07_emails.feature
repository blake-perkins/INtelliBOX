Feature: Email list and email detail
  As a team member
  I want to view emails and navigate to their associated actions
  So that I can understand the full context of each action item

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

  Scenario: View email detail page
    Given an email exists with subject "Detailed email subject"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "Detailed email subject"
    And the page contains "sender@example.com"

  Scenario: Email detail page shows related actions
    Given an unassigned "high" priority action exists with title "Action from this email"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "Action from this email"

  Scenario: Email detail shows Create Action button
    Given an email exists with subject "Email needing manual action"
    When I navigate to the email detail page
    Then the response status is 200
    And the page contains "Create Action"

  Scenario: View email detail for non-existent email
    Given the database is empty
    When I navigate to "/emails/99999"
    Then the response status is 404

  Scenario: Paginate emails list
    Given an email exists with subject "Paged email"
    When I navigate to "/emails?page=1"
    Then the response status is 200

  Scenario: Invalid page number for emails returns error
    Given the database is empty
    When I navigate to "/emails?page=0"
    Then the response status is 422
