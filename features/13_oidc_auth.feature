Feature: OIDC Authentication
  As a team member using SSO
  I want to sign in via my organization's identity provider
  So that I don't need a separate INtelliBOX password

  @smoke
  Scenario: Login page shows password form when auth is disabled
    When I navigate to "/auth/login"
    Then the response status is 200
    And the page contains "Username"
    And the page contains "Sign In"
