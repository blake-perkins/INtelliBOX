Feature: Program roster management
  As an administrator
  I want to manage the list of team members
  So that actions can be assigned to the right people

  Scenario: View roster page with no members
    Given the database is empty
    When I navigate to "/roster"
    Then the response status is 200

  Scenario: View roster page shows existing members
    Given a roster member "John" "Doe" with email "john@example.com" exists
    When I navigate to "/roster"
    Then the response status is 200
    And the page contains "john@example.com"

  Scenario: Add a new roster member
    Given the database is empty
    When I add a roster member with first "Jane" last "Smith" email "jane@example.com"
    Then the response status is 303
    And the roster member is saved in the database

  Scenario: Delete a roster member
    Given a roster member "Del" "Me" with email "del@example.com" exists
    When I delete the roster member
    Then the response status is 303
    And the roster member is removed from the database

  Scenario: Adding a duplicate roster member is rejected
    Given a roster member "Dup" "User" with email "dup@example.com" exists
    When I add a roster member with first "Dup" last "User" email "dup@example.com"
    Then the response status is 303

  Scenario: Team member appears in action assign dropdown
    Given an unassigned "high" priority action exists with title "Assign to roster member"
    And a roster member "Team" "Member" with email "team@example.com" exists
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Member, Team"
