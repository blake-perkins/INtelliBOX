Feature: Knowledge base document management
  As a program manager
  I want to upload and manage program documents
  So that AI can use them as context for better insights

  @smoke
  Scenario: View empty knowledge base
    Given the database is empty
    When I navigate to "/knowledge-base"
    Then the response status is 200
    And the page contains "No documents uploaded"

  Scenario: View knowledge base page
    Given a knowledge document "report.pdf" exists with description "Monthly report"
    When I navigate to "/knowledge-base"
    Then the response status is 200
    And the page contains "report.pdf"
    And the page contains "Monthly report"

  Scenario: Upload a text document
    Given the database is empty
    When I upload a TXT file "notes.txt" with content "Meeting notes from standup"
    Then the response redirects
    And the knowledge base has 1 document

  Scenario: Upload with description
    Given the database is empty
    When I upload a TXT file "sow.txt" with content "Statement of Work" described as "SOW v2"
    Then the response redirects
    And the knowledge base has 1 document

  Scenario: Reject unsupported file type
    Given the database is empty
    When I upload an unsupported file "virus.exe" to the knowledge base
    Then the response redirects
    And the knowledge base has 0 documents

  Scenario: Delete a document
    Given a knowledge document "old_doc.txt" exists
    When I delete knowledge document 1
    Then the response redirects
    And the knowledge base has 0 documents

  Scenario: Summary stats show document count
    Given a knowledge document "doc1.txt" exists
    And a knowledge document "doc2.txt" exists
    When I navigate to "/knowledge-base"
    Then the response status is 200
    And the page contains "2"
