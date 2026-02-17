Feature: Assign and manage action assignments
  As a team lead
  I want to assign actions to team members and track their status
  So that nothing falls through the cracks

  # --- Assign ---

  Scenario: Assign an unassigned action to a team member
    Given an unassigned "high" priority action exists with title "Assign this action"
    And a roster member "Carol" "White" with email "carol@example.com" exists
    When I assign the action to "carol@example.com"
    Then the response status is 303
    And the action assignment is saved in the database

  Scenario: Assign preserves action priority
    Given an unassigned "high" priority action exists with title "Priority preserved"
    When I assign the action to "someone@example.com"
    Then the response status is 303
    And the action priority is "high" in the database

  # --- Reassign ---

  Scenario: Reassign an already-assigned action to a different person
    Given an action titled "Reassign this" is assigned to "dave@example.com"
    And a roster member "Eve" "Brown" with email "eve@example.com" exists
    When I assign the action to "eve@example.com"
    Then the response status is 303
    And the action assignment is saved in the database
    And the action is assigned to "eve@example.com" in the database

  # --- Unassign ---

  Scenario: Unassign an action via edit form
    Given an action titled "Unassign this" is assigned to "frank@example.com"
    When I save a full edit form for the action
      | field       | value          |
      | title       | Unassign this  |
      | priority    | medium         |
      | assigned_to |                |
    Then the response status is 303
    And the action has no assignment in the database

  Scenario: Quick-unassign an action
    Given an action titled "Quick unassign" is assigned to "bob@example.com"
    When I quick-unassign the action
    Then the response status is 303
    And the action has no assignment in the database

  # --- Complete ---

  Scenario: Mark an assigned action as complete
    Given an action titled "Complete this" is assigned to "grace@example.com"
    When I mark the action as complete
    Then the response status is 303
    And the action is marked as "completed" in the database

  Scenario: Mark an unassigned action as complete creates assignment
    Given an unassigned "medium" priority action exists with title "Complete without assign"
    When I mark the action as complete
    Then the response status is 303
    And the action is marked as "completed" in the database

  # --- Reopen ---

  Scenario: Reopen a completed action
    Given a completed action titled "Reopen this" exists
    When I change the action status to "assigned"
    Then the response status is 303
    And the action is marked as "assigned" in the database

  # --- Status changes ---

  Scenario: Change status to completed via status endpoint
    Given an action titled "Status to complete" is assigned to "worker@example.com"
    When I change the action status to "completed"
    Then the response status is 303
    And the action is marked as "completed" in the database

  Scenario: Invalid status change is rejected
    Given an action titled "Bad status" is assigned to "worker@example.com"
    When I change the action status to "cancelled"
    Then the response status is 400

  # --- UI Elements ---

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

  Scenario: Action detail page shows Mark Complete button when assigned
    Given an action titled "Show complete button" is assigned to "worker@example.com"
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Mark Complete"

  Scenario: Action detail page shows Reopen button when completed
    Given a completed action titled "Show reopen button" exists
    When I navigate to the action detail page
    Then the response status is 200
    And the page contains "Reopen"

  Scenario: Action detail page does not show Mark Complete when unassigned
    Given an unassigned "medium" priority action exists with title "No complete button"
    When I navigate to the action detail page
    Then the response status is 200
    And the page does not contain "Mark Complete"
