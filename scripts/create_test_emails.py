"""Generate realistic test emails for EmailTools testing."""

import email
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path


def create_test_email(
    subject: str,
    from_addr: str,
    from_name: str,
    to_addr: str,
    body: str,
    message_id: str,
    date: datetime = None
) -> EmailMessage:
    """Create a test email message."""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f'"{from_name}" <{from_addr}>'
    msg['To'] = to_addr
    msg['Message-ID'] = message_id
    msg['Date'] = (date or datetime.now()).strftime('%a, %d %b %Y %H:%M:%S %z')
    msg.set_content(body)
    return msg


def save_email(msg: EmailMessage, filename: str, inbox_dir: Path):
    """Save email message to file."""
    filepath = inbox_dir / filename
    with open(filepath, 'wb') as f:
        f.write(msg.as_bytes())
    print(f"Created: {filename}")


def main():
    """Generate all test emails."""
    inbox_dir = Path("data/inbox")
    inbox_dir.mkdir(parents=True, exist_ok=True)

    # Clear existing files
    for file in inbox_dir.glob("*.eml"):
        file.unlink()

    today = datetime.now()

    # Email 1: High Priority RFI with specific due date
    email1 = create_test_email(
        subject="RFI #2024-045: Security Compliance Documentation Request",
        from_addr="john.smith@contractor.gov",
        from_name="John Smith",
        to_addr="programtracker@example.com",
        body="""Team,

We have received an urgent RFI from the customer regarding our security compliance posture.

ACTION REQUIRED: Please provide the following by February 20, 2026:
1. Current STIG compliance matrix
2. POA&M status report
3. Recent vulnerability scan results

This is HIGH PRIORITY as it's needed for the upcoming security audit.

Please assign someone to coordinate the response.

Best regards,
John Smith
Security Compliance Officer""",
        message_id="<rfi-2024-045@contractor.gov>",
        date=today - timedelta(hours=2)
    )
    save_email(email1, "rfi_security_compliance.eml", inbox_dir)

    # Email 2: Data Call with multiple items
    email2 = create_test_email(
        subject="DATA CALL: Monthly Metrics Report Due Feb 25",
        from_addr="sarah.johnson@agency.gov",
        from_name="Sarah Johnson",
        to_addr="programtracker@example.com",
        body="""Team,

Please submit the following metrics for January 2026 by February 25th:

1. System uptime percentage
2. Number of support tickets (open/closed)
3. User satisfaction survey results
4. Deployment frequency metrics
5. Mean time to recovery (MTTR)

This data will be included in the quarterly program review.

Thanks,
Sarah Johnson
Program Manager""",
        message_id="<datacall-jan2026@agency.gov>",
        date=today - timedelta(hours=5)
    )
    save_email(email2, "data_call_monthly_metrics.eml", inbox_dir)

    # Email 3: Stakeholder meeting request
    email3 = create_test_email(
        subject="Re: Need to schedule architecture review",
        from_addr="mike.williams@customer.mil",
        from_name="Mike Williams",
        to_addr="programtracker@example.com",
        body="""Hi team,

Following up on our last discussion - we need to schedule the quarterly architecture review.

Can someone coordinate finding a time in the next two weeks that works for all stakeholders? We'll need:
- Technical lead
- Security architect
- DevOps lead
- Product owner

Looking at March 1-15 timeframe. Medium priority but don't want it to slip.

Regards,
Mike Williams
Chief Architect""",
        message_id="<arch-review-2026@customer.mil>",
        date=today - timedelta(hours=8)
    )
    save_email(email3, "stakeholder_meeting_request.eml", inbox_dir)

    # Email 4: Bug report requiring investigation
    email4 = create_test_email(
        subject="URGENT: Production Issue - Login failures increasing",
        from_addr="alerts@monitoring.example.com",
        from_name="System Monitoring",
        to_addr="programtracker@example.com",
        body="""ALERT: Production system issue detected

Login failure rate has increased from 2% to 15% over the past hour.

ACTION NEEDED:
- Investigate root cause immediately
- Implement hotfix if identified
- Provide status update within 2 hours

Affected users: ~500
Start time: 2026-02-16 08:30 UTC

This is a HIGH PRIORITY production issue.

Dashboard: https://monitoring.example.com/dashboard/prod-login""",
        message_id="<alert-login-failures@monitoring.example.com>",
        date=today - timedelta(minutes=30)
    )
    save_email(email4, "urgent_production_issue.eml", inbox_dir)

    # Email 5: Request for proposal input
    email5 = create_test_email(
        subject="Input needed for contract renewal proposal",
        from_addr="jessica.martinez@contracts.gov",
        from_name="Jessica Martinez",
        to_addr="programtracker@example.com",
        body="""Team,

We're preparing the proposal for the FY2027 contract renewal and need technical input from your team.

Please provide by March 5th:
- Proposed technical approach for next year
- Resource estimates (FTEs and infrastructure)
- Key risks and mitigation strategies

This will feed into the larger proposal effort. Let me know if you have questions.

Jessica Martinez
Contracts Manager""",
        message_id="<proposal-fy2027@contracts.gov>",
        date=today - timedelta(days=1)
    )
    save_email(email5, "proposal_input_request.eml", inbox_dir)

    # Email 6: Customer feedback requiring response
    email6 = create_test_email(
        subject="Customer feedback on latest release",
        from_addr="robert.chen@customer.mil",
        from_name="Robert Chen",
        to_addr="programtracker@example.com",
        body="""Hi team,

We've received feedback from end users on the v3.2 release:

Positive:
- New dashboard is much more intuitive
- Performance improvements are noticeable

Issues raised:
- Export feature is missing CSV format option
- Some users reporting timeout on large data sets
- Need better documentation for the new API endpoints

Can someone review this feedback and provide a response plan? Not urgent but would like to address in the next sprint.

Thanks,
Robert Chen
Product Owner""",
        message_id="<feedback-v32@customer.mil>",
        date=today - timedelta(days=2)
    )
    save_email(email6, "customer_feedback.eml", inbox_dir)

    # Email 7: Simple FYI (should extract no actions)
    email7 = create_test_email(
        subject="FYI: Scheduled maintenance window next Sunday",
        from_addr="ops@example.com",
        from_name="Operations Team",
        to_addr="programtracker@example.com",
        body="""Team,

This is just an FYI that we have scheduled maintenance next Sunday, February 23rd from 2am-6am EST.

Systems will be unavailable during this window. This has already been coordinated with all stakeholders and approved.

No action required from your team.

Ops Team""",
        message_id="<maint-window-feb23@example.com>",
        date=today - timedelta(hours=10)
    )
    save_email(email7, "fyi_maintenance.eml", inbox_dir)

    # Email 8: Training coordination request
    email8 = create_test_email(
        subject="Need volunteers for new hire onboarding sessions",
        from_addr="hr@example.com",
        from_name="HR Department",
        to_addr="programtracker@example.com",
        body="""Hi team,

We have 5 new developers starting on March 1st and need team members to help with technical onboarding.

Looking for volunteers to:
1. Give 1-hour overview of system architecture (March 1, 10am)
2. Walk through development environment setup (March 1, 2pm)
3. Pair programming sessions throughout first week

Please let me know if you can help with any of these by February 20th.

Thanks!
HR Team""",
        message_id="<onboarding-march@hr.example.com>",
        date=today - timedelta(days=3)
    )
    save_email(email8, "training_coordination.eml", inbox_dir)

    # Email 9: Documentation update request
    email9 = create_test_email(
        subject="API documentation needs updating",
        from_addr="tech.writer@example.com",
        from_name="Emma Wilson",
        to_addr="programtracker@example.com",
        body="""Team,

I noticed the API documentation on the wiki is out of date with the recent v3.2 release.

Can someone from the dev team review and update the following pages by end of month:
- Authentication endpoints
- Data export API
- Webhooks documentation

Low priority but we're getting questions from external developers.

Emma Wilson
Technical Writer""",
        message_id="<docs-update@example.com>",
        date=today - timedelta(days=4)
    )
    save_email(email9, "documentation_update.eml", inbox_dir)

    # Email 10: License renewal coordination
    email10 = create_test_email(
        subject="Software licenses expiring - need inventory",
        from_addr="procurement@example.com",
        from_name="Procurement Team",
        to_addr="programtracker@example.com",
        body="""Team,

Several software licenses are up for renewal in Q2. To prepare the renewal request, we need an inventory of:

1. Which licenses are still being actively used
2. How many seats are needed for each
3. Any new tools you need to add

Please respond by February 28th so we can get the procurement package started. This affects multiple tools so please be thorough.

Procurement Team""",
        message_id="<license-renewal@procurement.example.com>",
        date=today - timedelta(days=5)
    )
    save_email(email10, "license_renewal.eml", inbox_dir)

    print(f"\nSuccessfully created 10 test emails in {inbox_dir}")
    print("\nExpected actions to extract:")
    print("  - High priority: 2 (RFI, production issue)")
    print("  - Medium priority: 4-5 (metrics, meeting, proposal, licenses)")
    print("  - Low priority: 2-3 (feedback, docs, training)")
    print("  - No actions: 1 (FYI maintenance)")


if __name__ == "__main__":
    main()
