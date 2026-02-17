Feature: Assign and manage action assignments
  As a team lead
  I want to assign actions to team members and track their status
  So that nothing falls through the cracks

  Scenario: Assign an unassigned action to a team member
    Given an unassigned "high" priority action exists with title "Assign this action"
    And a roster member "Carol" "White" with email "carol@example.com" exists
    When I assign the action to "carol@example.com"
    Then the response status is 303
    And the action assignment is saved in the database

  Scenario: Reassign an already-assigned action to a different person
    Given an action titled "Reassign this" is assigned to "dave@example.com"
    And a roster member "Eve" "Brown" with email "eve@example.com" exists
    When I assign the action to "eve@example.com"
    Then the response status is 303
    And the action assignment is saved in the database

  Scenario: Unassign an action via edit form
    Given an action titled "Unassign this" is assigned to "frank@example.com"
    When I save a full edit form for the action
      | field       | value          |
      | title       | Unassign this  |
      | priority    | medium         |
      | assigned_to |                |
    Then the response status is 303
    And the action has no assignment in the database

  Scenario: Mark an assigned action as complete
    Given an action titled "Complete this" is assigned to "grace@example.com"
    When I mark the action as complete
    Then the response status is 303
    And the action is marked as "completed" in the database

  Scenario: Action detail page shows roster dropdown when roster members exist
    Given an unassigned "medium" priority action exists with title "Ready to assign"
    And a roster member "Ivy" "Green" with email "ivy@example.com" exists
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Green, Ivy"

  Scenario: Action detail page shows add-team-members CTA when roster is empty
    Given an unassigned "medium" priority action exists with title "Nobody to assign to"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Add Team Members"
