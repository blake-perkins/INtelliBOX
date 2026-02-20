Feature: Program roster management
  As an administrator
  I want to manage the list of team members
  So that actions can be assigned to the right people

  # --- View Roster ---

  @smoke
  Scenario: View roster page with no members
    Given the database is empty
    When I navigate to "/roster"
    Then the response status is 200

  Scenario: View roster page shows existing members
    Given a roster member "John" "Doe" with email "john@example.com" exists
    When I navigate to "/roster"
    Then the response status is 200
    And the page contains "john@example.com"

  Scenario: Roster page shows member name
    Given a roster member "Jane" "Smith" with email "jane@example.com" exists
    When I navigate to "/roster"
    Then the response status is 200
    And the page contains "Jane"
    And the page contains "Smith"

  # --- Add Members ---

  Scenario: Add a new roster member
    Given the database is empty
    When I add a roster member with first "Jane" last "Smith" email "jane@example.com"
    Then the response status is 303
    And the roster member is saved in the database

  Scenario: Adding a duplicate roster member is rejected
    Given a roster member "Dup" "User" with email "dup@example.com" exists
    When I add a roster member with first "Dup" last "User" email "dup@example.com"
    Then the response status is 303

  # --- Delete Members ---

  Scenario: Delete a roster member
    Given a roster member "Del" "Me" with email "del@example.com" exists
    When I delete the roster member
    Then the response status is 303
    And the roster member is removed from the database

  # --- Roster in Action Dropdowns ---

  Scenario: Team member appears in action assign dropdown
    Given an unassigned "high" priority action exists with title "Assign to roster member"
    And a roster member "Team" "Member" with email "team@example.com" exists
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Member, Team"

  Scenario: Roster member appears in dashboard assign dropdown
    Given an unassigned "high" priority action exists with title "Dashboard roster test"
    And a roster member "Dash" "Board" with email "dash@example.com" exists
    When I navigate to "/"
    Then the response status is 200
    And the page contains "Board, Dash"

  Scenario: Roster member appears in actions list assign dropdown
    Given an unassigned "high" priority action exists with title "List roster test"
    And a roster member "List" "Member" with email "list@example.com" exists
    When I navigate to "/actions"
    Then the response status is 200
    And the page contains "Member, List"

  Scenario: Multiple roster members all appear in dropdown
    Given an unassigned "high" priority action exists with title "Multi roster test"
    And a roster member "Alpha" "One" with email "alpha@example.com" exists
    And a roster member "Beta" "Two" with email "beta@example.com" exists
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "One, Alpha"
    And the page contains "Two, Beta"
