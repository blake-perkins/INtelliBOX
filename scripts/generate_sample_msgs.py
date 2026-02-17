#!/usr/bin/env python3
"""
Generate sample .msg files for two purposes:
  1. tests/fixtures/sample_msgs/  — permanent examples for inspection
  2. data/inbox/                  — 50 realistic emails for live processing
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow import from tests/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from msg_factory import make_msg

# ---------------------------------------------------------------------------
# Realistic data pools
# ---------------------------------------------------------------------------

SENDERS = [
    ("Alice Chen", "alice.chen@acme-software.com"),
    ("Bob Martinez", "bob.martinez@acme-software.com"),
    ("Carol Wu", "carol.wu@acme-software.com"),
    ("David Park", "david.park@acme-software.com"),
    ("Emily Jones", "emily.jones@acme-software.com"),
    ("Frank Liu", "frank.liu@acme-software.com"),
    ("Grace Kim", "grace.kim@acme-software.com"),
    ("Hassan Ali", "hassan.ali@acme-software.com"),
    ("Irene Novak", "irene.novak@contractor.io"),
    ("James Torres", "james.torres@client-corp.com"),
    ("Karen Singh", "karen.singh@client-corp.com"),
    ("Leo Rossi", "leo.rossi@vendor-systems.net"),
    ("Mia Tanaka", "mia.tanaka@acme-software.com"),
    ("Nate Brown", "nate.brown@acme-software.com"),
    ("Olivia Scott", "olivia.scott@acme-software.com"),
]

TO = "inbox@acme-software.com"
CC_POOL = [
    "team-leads@acme-software.com",
    "engineering@acme-software.com",
    "ops@acme-software.com",
    "pm-group@acme-software.com",
]

BASE_DATE = datetime(2026, 2, 17, 8, 0, 0, tzinfo=timezone.utc)


def _date(hours_ago: int) -> datetime:
    return BASE_DATE - timedelta(hours=hours_ago)


# ---------------------------------------------------------------------------
# 1. Fixture samples — one of each interesting type
# ---------------------------------------------------------------------------

def generate_fixtures(out_dir: Path):
    """Create a curated set of .msg files for visual inspection."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Plain simple email
    make_msg(out_dir / "01_simple_bug_report.msg",
             message_id="<bug-4521@acme-software.com>",
             subject="BUG: Login page crashes on Safari 18",
             body="Hi team,\n\nThe login page is throwing a JS error on Safari 18.2.\n\nSteps to reproduce:\n1. Open https://app.acme.com/login in Safari 18\n2. Enter credentials\n3. Click Sign In\n4. Page goes blank with console error: TypeError null\n\nThis is blocking QA sign-off for v3.2.\n\n— Alice",
             sender_name="Alice Chen", sender_email="alice.chen@acme-software.com",
             to=TO, date=_date(2))

    # Email with CC
    make_msg(out_dir / "02_feature_request_with_cc.msg",
             message_id="<feat-890@client-corp.com>",
             subject="REQUEST: Export dashboard to PDF",
             body="Hello,\n\nOur executives need to share the analytics dashboard in PDF format for board meetings.\n\nCould you add a PDF export button to the dashboard page? Ideally with the company logo in the header.\n\nThis would be needed by March 1st.\n\nThanks,\nJames Torres\nClient Corp",
             sender_name="James Torres", sender_email="james.torres@client-corp.com",
             to=TO, cc="pm-group@acme-software.com; karen.singh@client-corp.com",
             date=_date(5))

    # Email chain (reply thread)
    make_msg(out_dir / "03_reply_chain.msg",
             message_id="<deploy-rc2@acme-software.com>",
             subject="RE: RE: v3.2 Release Candidate 2 — deploy schedule",
             body="Confirmed — deploying RC2 to staging at 3pm EST today.\n\nPlease hold off on merging feature branches until after the deploy.\n\n— Bob\n\nOn Mon, Feb 16, 2026 at 10:15 AM, Carol Wu wrote:\n> Can we push RC2 to staging today? QA is blocked.\n>\n> On Mon, Feb 16, 2026 at 9:00 AM, Bob Martinez wrote:\n>> RC2 is tagged and ready. CI is green.\n>> Let me know when staging is free.\n>>\n>> — Bob",
             sender_name="Bob Martinez", sender_email="bob.martinez@acme-software.com",
             to=TO, cc="carol.wu@acme-software.com",
             date=_date(1))

    # Forwarded message (Outlook style)
    make_msg(out_dir / "04_forwarded_outlook.msg",
             message_id="<fwd-sec-audit@acme-software.com>",
             subject="FW: Security audit findings — action required",
             body="FYI — forwarding the security audit results. We need to address the critical items by end of week.\n\n— David\n\n-----Original Message-----\nFrom: External Auditor <auditor@securityfirm.com>\nSent: Friday, February 14, 2026 4:30 PM\nTo: David Park <david.park@acme-software.com>\nSubject: Security audit findings — action required\n\nDavid,\n\nAttached are the results of our Q1 security audit. Summary of critical findings:\n\n1. SQL injection vulnerability in /api/search endpoint\n2. Missing rate limiting on authentication endpoints\n3. Session tokens not invalidated on password change\n\nPlease remediate items 1 and 2 within 5 business days.\n\nRegards,\nSecurity Firm LLC",
             sender_name="David Park", sender_email="david.park@acme-software.com",
             to=TO, cc="engineering@acme-software.com",
             date=_date(3))

    # Meeting follow-up with action items
    make_msg(out_dir / "05_meeting_action_items.msg",
             message_id="<sprint-retro-w7@acme-software.com>",
             subject="Sprint 7 Retro — Action Items",
             body="Hi all,\n\nHere are the action items from today's retro:\n\n1. Emily: Set up Datadog alerting for API latency > 2s (due Feb 20)\n2. Frank: Write runbook for database failover (due Feb 21)\n3. Grace: Schedule cross-team knowledge sharing session (due Feb 19)\n4. Hassan: Investigate flaky integration tests in CI (due Feb 18)\n\nPlease update JIRA tickets accordingly.\n\nThanks,\nMia",
             sender_name="Mia Tanaka", sender_email="mia.tanaka@acme-software.com",
             to=TO, cc="team-leads@acme-software.com",
             date=_date(4))

    # Urgent escalation
    make_msg(out_dir / "06_urgent_escalation.msg",
             message_id="<outage-20260217@acme-software.com>",
             subject="URGENT: Production database connection pool exhausted",
             body="INCIDENT IN PROGRESS\n\nProduction DB connection pool is at 100%. API response times are 30s+.\n\nImmediate actions needed:\n- Restart the API pods to clear stale connections\n- Investigate the long-running query from the batch job\n- Page on-call DBA\n\nI've already restarted 2 of 4 pods. Need someone to look at the batch job.\n\n— Nate (on-call)",
             sender_name="Nate Brown", sender_email="nate.brown@acme-software.com",
             to=TO, date=_date(0))

    # Vendor notification
    make_msg(out_dir / "07_vendor_notification.msg",
             message_id="<license-renewal-2026@vendor-systems.net>",
             subject="License renewal reminder — Vendor Systems Platform",
             body="Dear Acme Software,\n\nThis is a reminder that your Vendor Systems Platform license expires on March 15, 2026.\n\nCurrent plan: Enterprise (50 seats)\nRenewal cost: $24,000/year\n\nPlease contact your account manager to discuss renewal options.\n\nBest regards,\nLeo Rossi\nAccount Manager\nVendor Systems",
             sender_name="Leo Rossi", sender_email="leo.rossi@vendor-systems.net",
             to=TO, date=_date(8))

    # Email with HTML body
    make_msg(out_dir / "08_html_email.msg",
             message_id="<weekly-digest@acme-software.com>",
             subject="Weekly Engineering Digest — Feb 10-14",
             body="Weekly Engineering Digest\n\nHighlights:\n- v3.1.4 hotfix deployed successfully\n- New CI pipeline reduces build time by 40%\n- 3 new team members onboarded\n\nMetrics:\n- Uptime: 99.97%\n- Deploy frequency: 12 deploys\n- Mean time to recovery: 4 min",
             sender_name="Olivia Scott", sender_email="olivia.scott@acme-software.com",
             to=TO,
             html_body=b"<html><body><h1>Weekly Engineering Digest</h1><p><b>Highlights:</b></p><ul><li>v3.1.4 hotfix deployed successfully</li><li>New CI pipeline reduces build time by 40%</li><li>3 new team members onboarded</li></ul><p><b>Metrics:</b></p><table border='1'><tr><td>Uptime</td><td>99.97%</td></tr><tr><td>Deploy frequency</td><td>12 deploys</td></tr><tr><td>MTTR</td><td>4 min</td></tr></table></body></html>",
             date=_date(10))

    # Empty/minimal email
    make_msg(out_dir / "09_minimal_no_body.msg",
             message_id="<ping-test@acme-software.com>",
             subject="test",
             body="",
             sender_name="Frank Liu", sender_email="frank.liu@acme-software.com",
             to=TO, date=_date(12))

    # Duplicate candidate (same message-id, different sender)
    make_msg(out_dir / "10_duplicate_original.msg",
             message_id="<dup-demo-001@acme-software.com>",
             subject="Quarterly planning doc — please review",
             body="Team,\n\nPlease review the Q2 planning doc before Thursday's meeting.\n\nhttps://docs.acme.com/q2-plan\n\n— Grace",
             sender_name="Grace Kim", sender_email="grace.kim@acme-software.com",
             to=TO, date=_date(6))

    make_msg(out_dir / "10_duplicate_forwarded.msg",
             message_id="<dup-demo-001@acme-software.com>",
             subject="FW: Quarterly planning doc — please review",
             body="Forwarding to inbox for tracking.\n\n— Irene",
             sender_name="Irene Novak", sender_email="irene.novak@contractor.io",
             to=TO, date=_date(5))

    print(f"  Created {len(list(out_dir.glob('*.msg')))} fixture .msg files in {out_dir}")


# ---------------------------------------------------------------------------
# 2. Inbox emails — 50 realistic messages for live processing
# ---------------------------------------------------------------------------

INBOX_EMAILS = [
    # --- Bug reports (10) ---
    dict(id="bug-5001", subj="BUG: CSV export truncates columns over 255 chars",
         body="The CSV export from /reports is silently truncating any cell content over 255 characters. This is cutting off long descriptions.\n\nSteps:\n1. Create an action with a 300-char description\n2. Export to CSV\n3. Open in Excel — description is truncated\n\nPriority: High — client demo next week.",
         sender=0, hours=1),
    dict(id="bug-5002", subj="BUG: Timezone offset wrong in email timestamps",
         body="Emails received from EST senders are showing with UTC timestamps in the dashboard. The received_date column doesn't account for timezone offsets.\n\nExample: Email sent at 2:00 PM EST shows as 2:00 PM in the UI (should be 7:00 PM UTC or converted to local).",
         sender=1, hours=2),
    dict(id="bug-5003", subj="BUG: Search returns stale results after action update",
         body="After updating an action's assignee, the search results still show the old assignee until the page is hard-refreshed. Likely a caching issue with the search index.",
         sender=2, hours=3),
    dict(id="bug-5004", subj="BUG: Email parser crashes on .msg files with embedded images",
         body="Got a crash when processing a .msg file that had inline images. Stack trace:\n\nTraceback:\n  File parser.py, line 158\n  extract_msg.Message(path)\n  OLE2Error: cannot read stream\n\nThe email was from a client using Outlook with signature images.",
         sender=3, hours=4),
    dict(id="bug-5005", subj="BUG: Priority rules not applied to batch-processed emails",
         body="When emails come in as a batch (10+ at once), the priority rules from /settings don't seem to apply. Individual emails processed one at a time get the correct priority override.",
         sender=4, hours=5),
    dict(id="bug-5006", subj="BUG: Dark mode CSS breaks on report page",
         body="The report page tables have white text on white background when the browser is in dark mode. Need to add prefers-color-scheme media query or explicit background colors.",
         sender=5, hours=6),
    dict(id="bug-5007", subj="BUG: Duplicate detection fails for emails with angle brackets in message-id",
         body="Some mail servers send message IDs without angle brackets. When the same email arrives with <id@server> and id@server, we create two records instead of merging.",
         sender=6, hours=7),
    dict(id="bug-5008", subj="BUG: File watcher misses .msg files on network drives",
         body="The file watcher using watchdog doesn't pick up .msg files dropped onto mapped network drives (Z:\\inbox). Works fine for local paths. Might need polling fallback for UNC paths.",
         sender=7, hours=8),
    dict(id="bug-5009", subj="BUG: Action due dates parsed incorrectly from European date format",
         body="AI is extracting due dates wrong when the email says '15/03/2026' (European DD/MM). It's being stored as March being day 3 and month 15 (invalid). Need locale-aware date parsing.",
         sender=8, hours=9),
    dict(id="bug-5010", subj="BUG: Settings page 500 error when priority rules JSON is malformed",
         body="If someone manually edits the settings table and puts invalid JSON in the priority_rules value, the /settings page throws a 500 error instead of showing a validation message.\n\nReproduction: UPDATE settings SET value='{bad' WHERE key='priority_rules';",
         sender=9, hours=10),

    # --- Feature requests (8) ---
    dict(id="feat-2001", subj="REQUEST: Slack integration for new action notifications",
         body="Can we get Slack notifications when new high-priority actions are created? Ideally posting to #engineering-actions with the action summary and a link to the detail page.\n\nWe're using Slack webhooks for other tools so this should be straightforward.",
         sender=10, hours=11),
    dict(id="feat-2002", subj="REQUEST: Bulk assign actions to team members",
         body="Right now we have to assign actions one at a time. When 20 actions come in from a single email, it's tedious. Please add checkboxes and a bulk assign dropdown.\n\nBonus: auto-assign based on keyword rules (e.g., 'database' → DBA team).",
         sender=0, hours=12),
    dict(id="feat-2003", subj="REQUEST: Email template for weekly report",
         body="The nightly report is great but we need a weekly summary too. Could we get a configurable report schedule (daily/weekly/monthly) with customizable templates?\n\nWeekly should show trends: actions opened vs closed, average time to assign.",
         sender=11, hours=13),
    dict(id="feat-2004", subj="REQUEST: API endpoint for external integrations",
         body="Our JIRA workflow needs to pull action data from INtelliBOX. Can we get a REST API with:\n\nGET /api/actions?status=open&priority=high\nGET /api/actions/:id\nPOST /api/actions/:id/assign\n\nJSON responses, API key auth.",
         sender=1, hours=14),
    dict(id="feat-2005", subj="REQUEST: Archive and retention policy",
         body="We're accumulating emails and actions with no cleanup. Need:\n1. Auto-archive completed actions after 90 days\n2. Purge raw .msg files after 180 days\n3. Configurable retention periods in /settings\n4. Manual archive button on action detail page",
         sender=2, hours=15),
    dict(id="feat-2006", subj="REQUEST: Mobile-responsive dashboard",
         body="The dashboard is unusable on phones. The table columns overflow and the sidebar covers the content. Need responsive CSS or a simplified mobile view for on-call engineers checking actions from their phones.",
         sender=3, hours=16),
    dict(id="feat-2007", subj="REQUEST: Custom action categories",
         body="The current categories (Bug, Feature, Task, etc.) don't match our workflow. We need:\n- Incident\n- Change Request\n- Compliance\n- Customer Escalation\n\nPlease make categories configurable in /settings.",
         sender=4, hours=17),
    dict(id="feat-2008", subj="REQUEST: Email threading — group related actions",
         body="When a reply chain generates multiple actions across different emails, there's no way to see they're related. Can we link actions that share the same email thread (In-Reply-To header)?",
         sender=5, hours=18),

    # --- Deployment / ops (7) ---
    dict(id="deploy-3001", subj="Deploy v3.2.0-rc3 to staging — approval needed",
         body="RC3 is tagged and CI is green. Changes since RC2:\n- Fix: Safari login crash (BUG-4521)\n- Fix: CSV export truncation (BUG-5001)\n- Feature: PDF export button\n\nRequesting approval to deploy to staging at 2pm EST.\n\nRollback plan: revert to v3.1.4 tag.",
         sender=1, hours=19),
    dict(id="deploy-3002", subj="Post-deploy verification — v3.2.0-rc3 staging",
         body="Staging deploy complete. Verification checklist:\n[x] Health check endpoint returns 200\n[x] Login flow works (Chrome, Firefox, Safari)\n[x] CSV export includes full-length columns\n[ ] PDF export — needs manual QA\n[ ] Load test — scheduled for tonight\n\nNo blockers so far.",
         sender=1, hours=17),
    dict(id="deploy-3003", subj="ALERT: Staging disk usage at 92%",
         body="Automated alert: staging server disk usage is at 92%.\n\nLargest directories:\n/var/log/app — 12GB (log rotation not configured)\n/tmp/uploads — 8GB (orphaned temp files)\n\nAction needed: configure log rotation, clean up /tmp/uploads, consider expanding volume.",
         sender=12, hours=20),
    dict(id="deploy-3004", subj="Database migration plan for v3.2 release",
         body="The v3.2 release includes 3 schema migrations:\n\n1. 006_add_also_received_from — adds TEXT column to emails table\n2. 007_add_action_categories — adds category column with default values\n3. 008_add_retention_settings — new settings rows\n\nMigration 1 is backward-compatible. Migrations 2-3 need coordinated deploy.\n\nEstimated downtime: 30 seconds for schema changes.\n\nPlease review and approve.",
         sender=6, hours=21),
    dict(id="deploy-3005", subj="SSL certificate renewal — expires March 1",
         body="The wildcard SSL cert for *.acme-software.com expires March 1, 2026.\n\nAction items:\n1. Generate new CSR\n2. Submit to DigiCert (2 business day turnaround)\n3. Install on load balancer\n4. Verify with openssl s_client\n\nDeadline: February 26 to allow buffer time.",
         sender=7, hours=22),
    dict(id="deploy-3006", subj="Capacity planning — Q2 projections",
         body="Based on Q1 growth:\n- Email volume: 150/day → projected 250/day in Q2\n- Database size: 2.1GB → projected 4.5GB\n- API requests: 50k/day → projected 85k/day\n\nRecommendations:\n1. Upgrade RDS instance from db.t3.medium to db.t3.large\n2. Add second API pod\n3. Implement Redis caching for dashboard queries",
         sender=13, hours=23),
    dict(id="deploy-3007", subj="Runbook: Database failover procedure",
         body="As requested in Sprint 7 retro, here's the DB failover runbook:\n\n1. Confirm primary is unhealthy: check RDS console + CloudWatch\n2. Promote read replica: aws rds promote-read-replica\n3. Update connection string in Parameter Store\n4. Restart API pods: kubectl rollout restart deployment/api\n5. Verify: run health check + test login flow\n6. Notify team in #engineering Slack channel\n\nETA for full failover: ~5 minutes.\n\nPlease review and add to Confluence.",
         sender=5, hours=24),

    # --- Reply chains / forwards (8) ---
    dict(id="chain-4001", subj="RE: Code review for PR #347 — auth refactor",
         body="Approved with one comment — the token refresh logic should handle network timeouts gracefully. Added inline comment on the PR.\n\n— Carol\n\nOn Mon, Feb 16, 2026, Bob Martinez wrote:\n> PR #347 is ready for review. Key changes:\n> - Moved from session-based to JWT auth\n> - Added refresh token rotation\n> - Updated all middleware\n>\n> Tests are passing, coverage at 89%.",
         sender=2, hours=25),
    dict(id="chain-4002", subj="RE: RE: RE: Client onboarding timeline",
         body="Updated the timeline doc. We're now targeting March 10 for go-live.\n\n— Karen\n\nOn Feb 15, James Torres wrote:\n> Can we push it back a week? Their IT team needs more time for SSO setup.\n>\n> On Feb 14, Karen Singh wrote:\n>> The client is asking about the onboarding timeline. Original target was March 3.\n>> Can everyone confirm their deliverables are on track?\n>>\n>> On Feb 13, Emily Jones wrote:\n>>> I've drafted the onboarding plan. See attached.\n>>> Integration testing: Feb 24-28\n>>> UAT: March 1-3\n>>> Go-live: March 3",
         sender=10, hours=26),
    dict(id="chain-4003", subj="FW: Compliance audit — data retention questions",
         body="Forwarding for awareness. We need to answer these questions by Friday.\n\n— David\n\n-----Original Message-----\nFrom: compliance@audit-firm.com\nSent: Thursday, February 13, 2026 2:15 PM\nTo: David Park\nSubject: Data retention questions\n\nDavid,\n\nAs part of the SOC 2 audit, we need documentation for:\n1. How long are email files retained?\n2. Are emails encrypted at rest?\n3. Who has access to raw email data?\n4. Is there an audit trail for data access?\n\nPlease provide by February 21.",
         sender=3, hours=27),
    dict(id="chain-4004", subj="RE: Performance test results — API latency",
         body="Good results overall. The P99 latency for /api/actions is still above 2s target though. I think we need to add an index on (status, priority) to the actions table.\n\n— Hassan\n\nOn Feb 16, Olivia Scott wrote:\n> Load test results for v3.2-rc3:\n> - P50 latency: 120ms (target: <200ms) ✓\n> - P95 latency: 450ms (target: <1s) ✓\n> - P99 latency: 2.3s (target: <2s) ✗\n> - Max concurrent users: 500\n> - Error rate: 0.02%",
         sender=7, hours=28),
    dict(id="chain-4005", subj="FW: Vendor price increase notification",
         body="Heads up — our monitoring vendor is raising prices 15%. Need to evaluate alternatives or negotiate.\n\n— Grace\n\n_____________________________________________\nFrom: billing@monitoring-vendor.com\nSent: February 12, 2026\nTo: grace.kim@acme-software.com\nSubject: Pricing update effective April 1\n\nDear Customer,\n\nWe're writing to inform you of a pricing adjustment effective April 1, 2026.\nYour current plan ($800/mo) will increase to $920/mo.\n\nPlease contact your account manager to discuss options.",
         sender=6, hours=29),

    # --- Duplicates (same message forwarded by multiple people) (5) ---
    dict(id="dup-6001", subj="IMPORTANT: Production freeze starts Friday 5pm",
         body="All teams: production freeze begins Friday Feb 20 at 5pm EST through Monday 8am.\n\nNo deploys, no database changes, no infrastructure modifications during the freeze window.\n\nEmergency hotfixes require VP approval.\n\n— Mia (Release Manager)",
         sender=12, hours=30),
    dict(id="dup-6001", subj="FW: IMPORTANT: Production freeze starts Friday 5pm",
         body="Make sure everyone sees this.\n\n— Alice",
         sender=0, hours=29),
    dict(id="dup-6001", subj="FW: IMPORTANT: Production freeze starts Friday 5pm",
         body="Forwarding to inbox for tracking.\n\n— Bob",
         sender=1, hours=28),
    dict(id="dup-6001", subj="FW: IMPORTANT: Production freeze starts Friday 5pm",
         body="FYI — sharing with the broader team.\n\n— Irene",
         sender=8, hours=27),
    dict(id="dup-6001", subj="FW: IMPORTANT: Production freeze starts Friday 5pm",
         body="Forwarding.\n\n— Emily",
         sender=4, hours=26),

    # --- Miscellaneous (12) ---
    dict(id="misc-7001", subj="Team offsite — March 20-21 logistics",
         body="Hi all,\n\nThe engineering offsite is confirmed for March 20-21 at the downtown conference center.\n\nLogistics:\n- Hotel: Block reserved at Marriott (code ACME2026)\n- Agenda: Strategy sessions Day 1, hackathon Day 2\n- Dinner: 7pm at Chez Restaurant\n\nPlease RSVP by Feb 28 and book your hotel.\n\nAction items:\n1. Everyone: RSVP and book hotel by Feb 28\n2. Team leads: Submit hackathon project proposals by March 10\n3. Olivia: Finalize catering order by March 15",
         sender=12, hours=31),
    dict(id="misc-7002", subj="New hire starting Monday — setup checklist",
         body="Reminder: Sarah Park (frontend engineer) starts Monday.\n\nSetup needed:\n1. Hassan: Create GitHub account and add to acme-software org\n2. Frank: Provision AWS IAM credentials (read-only)\n3. Grace: Add to Slack channels (#engineering, #frontend, #standup)\n4. Mia: Schedule 1:1 onboarding meetings for first week\n\nPlease complete by Friday EOD.",
         sender=13, hours=32),
    dict(id="misc-7003", subj="Quarterly security training — mandatory completion",
         body="All engineering staff must complete the Q1 security awareness training by February 28.\n\nLink: https://training.acme.com/security-q1-2026\nEstimated time: 45 minutes\n\nCompletion is tracked automatically. Managers will receive a report of incomplete training on March 1.\n\nThis is a compliance requirement.",
         sender=14, hours=33),
    dict(id="misc-7004", subj="Tech debt sprint proposal — March 3-14",
         body="I'm proposing a dedicated tech debt sprint for the first two weeks of March.\n\nProposed focus areas:\n1. Upgrade Python 3.12 → 3.13 across all services\n2. Replace deprecated SQLAlchemy patterns\n3. Consolidate 3 overlapping utility libraries\n4. Add structured logging (JSON format) for all services\n5. Fix the 47 suppressed linter warnings\n\nROI: Reduced CI time, fewer dependency conflicts, better observability.\n\nPlease vote +1 or raise concerns by Thursday.",
         sender=13, hours=34),
    dict(id="misc-7005", subj="On-call rotation change — effective March 1",
         body="Updated on-call rotation starting March 1:\n\nWeek 1: Bob + Emily (primary/secondary)\nWeek 2: Hassan + Carol (primary/secondary)\nWeek 3: Frank + Nate (primary/secondary)\nWeek 4: Grace + Alice (primary/secondary)\n\nReminders:\n- Primary carries the pager\n- Secondary is backup if primary is unavailable\n- Swap requests need 48h notice\n\nUpdated PagerDuty schedule: https://pagerduty.acme.com/schedule/eng",
         sender=14, hours=35),
    dict(id="misc-7006", subj="Third-party dependency audit results",
         body="Ran npm audit and pip audit across all services. Results:\n\nCritical: 0\nHigh: 2 (both in lodash — already patched in 4.17.22)\nMedium: 5 (various, non-exploitable in our context)\nLow: 12\n\nAction items:\n1. Update lodash to 4.17.22 in frontend (Bob)\n2. Review medium findings — schedule fixes for tech debt sprint\n3. Document accepted risks for low findings\n\nFull report: https://docs.acme.com/dep-audit-q1-2026",
         sender=7, hours=36),
    dict(id="misc-7007", subj="CI pipeline optimization results",
         body="Completed the CI pipeline optimization work. Before/after:\n\n| Stage | Before | After |\n|-------|--------|-------|\n| Install deps | 3m 20s | 1m 10s |\n| Lint + typecheck | 2m 15s | 0m 45s |\n| Unit tests | 4m 30s | 2m 00s |\n| Integration tests | 6m 00s | 3m 30s |\n| Build + push | 2m 00s | 1m 15s |\n| TOTAL | 18m 05s | 8m 40s |\n\nKey changes: parallel test execution, dependency caching, incremental builds.\n\n52% reduction in total pipeline time.",
         sender=14, hours=37),
    dict(id="misc-7008", subj="Customer escalation — Client Corp data discrepancy",
         body="Client Corp is reporting that their action counts don't match between our dashboard and their JIRA integration.\n\nTheir numbers: 47 open actions\nOur dashboard: 52 open actions\n\nDifference of 5 — likely actions that were closed in JIRA but not synced back.\n\nThis is a P1 for them. They have a board meeting Thursday.\n\nAction: investigate the sync gap and provide root cause by EOD tomorrow.",
         sender=9, hours=38),
    dict(id="chain-4006", subj="RE: Database index recommendation",
         body="Added the composite index. Query time dropped from 2.3s to 180ms.\n\nCREATE INDEX idx_actions_status_priority ON actions(status, priority);\n\n— Hassan\n\nOn Feb 16, Nate Brown wrote:\n> Good call on the index. Can you also check if we need one on\n> (email_id, created_at) for the processing log queries?\n>\n> On Feb 16, Hassan Ali wrote:\n>> The P99 latency issue is definitely the actions table.\n>> EXPLAIN shows a full table scan on status + priority filters.\n>> Recommending a composite index.",
         sender=7, hours=39),
    dict(id="misc-7009", subj="Documentation sprint results — 23 pages updated",
         body="Completed the documentation sprint. Summary:\n\n- API docs: 8 endpoints documented with examples\n- Runbooks: 5 new runbooks (deploy, failover, rollback, scaling, monitoring)\n- Architecture: Updated system diagram with new services\n- Onboarding: Refreshed new-hire guide\n- README: Updated setup instructions for Python 3.12\n\nTotal: 23 pages created/updated in Confluence.\n\nNext: schedule quarterly doc review to keep them current.",
         sender=14, hours=40),
    dict(id="misc-7010", subj="Budget approval needed — monitoring tool upgrade",
         body="Requesting budget approval for upgrading our monitoring stack:\n\nCurrent: Basic plan ($800/mo)\nProposed: Pro plan ($1,400/mo)\n\nWhat we get:\n- Custom dashboards (currently limited to 5)\n- 13-month data retention (currently 30 days)\n- Anomaly detection (saves on-call time)\n- SSO integration\n\nROI: Estimated 10 hours/month saved in manual monitoring.\n\nNeed VP sign-off. Can we discuss at Thursday's budget meeting?",
         sender=6, hours=41),
    dict(id="misc-7011", subj="Incident post-mortem — Feb 15 API outage",
         body="Post-mortem for the 23-minute API outage on Feb 15:\n\nTimeline:\n- 14:32 — Alert fired: API error rate > 5%\n- 14:35 — On-call acknowledged, began investigation\n- 14:38 — Root cause identified: DB connection pool exhausted\n- 14:42 — Mitigation: restarted API pods\n- 14:45 — Partial recovery\n- 14:55 — Full recovery confirmed\n\nRoot cause: Long-running analytics query held 45 connections for 12 minutes.\n\nAction items:\n1. Add statement_timeout = 30s to analytics queries (Frank, due Feb 20)\n2. Set up connection pool monitoring alert (Nate, due Feb 19)\n3. Move analytics to read replica (Hassan, due March 1)\n4. Update runbook with connection pool recovery steps (Bob, due Feb 21)",
         sender=13, hours=42),
    dict(id="misc-7012", subj="Accessibility audit — WCAG 2.1 compliance gaps",
         body="Ran an accessibility audit with axe-core on all pages. Findings:\n\nCritical (3):\n1. Action detail page missing form labels — screen readers can't identify fields\n2. Color contrast ratio below 4.5:1 on status badges\n3. No skip-to-content link on any page\n\nSerious (7):\n- Missing alt text on logo and chart images\n- Tab order incorrect on settings page\n- Modal dialogs don't trap focus\n- Dropdown menus not keyboard-navigable\n\nWe need to fix the critical items before the March release. Legal says WCAG 2.1 AA compliance is contractually required for Client Corp.\n\nI'll create JIRA tickets for each finding.",
         sender=14, hours=43),
    dict(id="misc-7013", subj="RE: Staging environment rebuild request",
         body="Staging rebuild is complete. New environment details:\n\n- URL: https://staging.acme-software.com\n- DB: staging-db.cluster-abc123.us-east-1.rds.amazonaws.com\n- Redis: staging-redis.abc123.cache.amazonaws.com\n- Deployed version: v3.2.0-rc3\n\nAll data wiped per request. Seed data loaded from fixtures.\n\n— Frank\n\nOn Feb 16, Carol Wu wrote:\n> Can we get a fresh staging environment? The current one has corrupted\n> test data from the load test and it's causing false failures in QA.\n>\n> Please wipe and rebuild with clean seed data.",
         sender=5, hours=44),
    dict(id="misc-7014", subj="Open source license review — new dependencies",
         body="Reviewed licenses for the 4 new dependencies added in v3.2:\n\n1. extract-msg v0.55.0 — MIT ✓\n2. python-pptx v0.6.23 — MIT ✓\n3. weasyprint v62.1 — BSD-3-Clause ✓\n4. redis-py v5.2.0 — MIT ✓\n\nAll compatible with our Apache 2.0 license. No copyleft or restrictive licenses.\n\nApproved for production use.",
         sender=6, hours=45),
]


def generate_inbox(out_dir: Path):
    """Create 50 .msg files in data/inbox for live processing."""
    out_dir.mkdir(parents=True, exist_ok=True)

    seen_ids: dict[str, int] = {}
    for i, e in enumerate(INBOX_EMAILS):
        sender_name, sender_email = SENDERS[e["sender"] % len(SENDERS)]
        msg_id = f"<{e['id']}@acme-software.com>"
        cc = CC_POOL[i % len(CC_POOL)] if i % 3 == 0 else ""

        # Create a filename that sorts nicely — add suffix for duplicate IDs
        safe_id = e["id"]
        seen_ids[safe_id] = seen_ids.get(safe_id, 0) + 1
        if seen_ids[safe_id] > 1:
            safe_id = f"{safe_id}_fwd{seen_ids[safe_id] - 1}"
        make_msg(
            out_dir / f"{safe_id}.msg",
            message_id=msg_id,
            subject=e["subj"],
            body=e["body"],
            sender_name=sender_name,
            sender_email=sender_email,
            to=TO,
            cc=cc,
            date=_date(e["hours"]),
        )

    count = len(list(out_dir.glob("*.msg")))
    print(f"  Created {count} inbox .msg files in {out_dir}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating sample .msg files...\n")

    fixtures_dir = ROOT / "tests" / "fixtures" / "sample_msgs"
    inbox_dir = ROOT / "data" / "inbox"

    print("[1/2] Fixture samples:")
    generate_fixtures(fixtures_dir)

    print(f"\n[2/2] Inbox emails:")
    generate_inbox(inbox_dir)

    print(f"\nDone! Drop into the app to process the inbox emails.")
