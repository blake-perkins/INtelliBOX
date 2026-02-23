#!/bin/bash
# Seed the pilot instance with test data.
# Run from local machine:
#   bash scripts/seed_pilot.sh <EC2_IP>
#
# Creates: roster members, knowledge base docs, copies sample emails, processes them.
set -euo pipefail

IP="${1:?Usage: bash scripts/seed_pilot.sh <EC2_IP>}"
KEY="${SSH_KEY:-$HOME/Downloads/intellibox-key.pem}"

ssh_cmd() { ssh -i "$KEY" "ubuntu@$IP" "$1"; }

echo "=== Seeding pilot at $IP ==="

# ── 1. Copy sample .eml files to the inbox ────────────────────────────────
echo ""
echo "--- Copying sample emails to inbox ---"
ssh_cmd "sudo cp /home/ubuntu/INtelliBOX/tests/fixtures/sample_emails/*.eml /opt/intellibox/data/inbox/"

# ── 2. Create roster members via Python inside the container ──────────────
echo ""
echo "--- Creating roster members ---"
ssh_cmd "sudo podman exec intellibox python -c \"
import sys; sys.path.insert(0, '/app/src')
from intellibox.database import get_session
from intellibox.models import RosterMember

members = [
    ('Alice', 'Chen', 'alice.chen@acme-software.com'),
    ('Bob', 'Martinez', 'bob.martinez@acme-software.com'),
    ('Carol', 'Wu', 'carol.wu@acme-software.com'),
    ('David', 'Park', 'david.park@acme-software.com'),
    ('Emily', 'Jones', 'emily.jones@acme-software.com'),
    ('Blake', 'Perkins', 'bperkins@example.com'),
]

with get_session() as s:
    existing = {r.email for r in s.query(RosterMember).all()}
    added = 0
    for first, last, email in members:
        if email not in existing:
            s.add(RosterMember(first_name=first, last_name=last, email=email))
            added += 1
    s.commit()
    print(f'Roster: {added} added, {len(existing)} already existed')
\""

# ── 3. Create knowledge base documents ────────────────────────────────────
echo ""
echo "--- Creating knowledge base documents ---"
ssh_cmd "sudo podman exec intellibox python -c \"
import sys; sys.path.insert(0, '/app/src')
from intellibox.database import get_session
from intellibox.models import KnowledgeDocument

docs = [
    {
        'filename': 'team_sop.txt',
        'file_type': 'txt',
        'description': 'Standard Operating Procedures for the INtelliBOX pilot team',
        'extracted_text': '''INtelliBOX Pilot Team — Standard Operating Procedures

1. EMAIL TRIAGE
   - All emails from client-corp.com addresses are HIGH priority
   - Security-related emails (containing 'vulnerability', 'CVE', 'incident') are always HIGH priority
   - Vendor notifications are LOW priority unless they mention 'renewal' or 'expiration'
   - Weekly status reports are MEDIUM priority

2. ASSIGNMENT RULES
   - Security items go to Carol Wu
   - Client escalations go to Alice Chen (account lead)
   - Infrastructure / deployment tasks go to David Park
   - Feature requests go to Bob Martinez (product lead)
   - Documentation tasks go to Emily Jones

3. DUE DATE GUIDELINES
   - HIGH priority items: 2 business days from receipt
   - MEDIUM priority items: 5 business days from receipt
   - LOW priority items: 10 business days or next sprint

4. ESCALATION PATH
   - If an action is unassigned for >24 hours, escalate to Blake Perkins
   - If a HIGH priority item is not in_progress within 4 hours, notify team leads
''',
    },
    {
        'filename': 'project_context.txt',
        'file_type': 'txt',
        'description': 'Acme Software project context and key stakeholders',
        'extracted_text': '''Acme Software — Project Context

PROJECT: NextGen Platform v3.2
CLIENT: Client Corp (James Torres — primary contact, Karen Singh — technical lead)
VENDOR: Vendor Systems (Leo Rossi — account manager)
CONTRACTOR: Irene Novak (contractor.io) — security auditor

CURRENT SPRINT: Sprint 14 (Feb 17 — Feb 28, 2026)
RELEASE TARGET: March 15, 2026

KEY MILESTONES:
- Feb 20: Security audit report due (Irene Novak)
- Feb 25: API v3 feature freeze
- Feb 28: Sprint 14 demo to Client Corp
- Mar 1: Performance testing begins
- Mar 10: Release candidate 1
- Mar 15: Production deployment

KNOWN RISKS:
- Database migration from v3.1 to v3.2 requires 4-hour maintenance window
- SSL certificates for staging expire March 5 — must renew before RC1
- Vendor license renewal due by end of February
- Client Corp requested custom reporting feature — not yet scoped

TEAM CAPACITY:
- Alice Chen: 80% (account management overhead)
- Bob Martinez: 100%
- Carol Wu: 60% (shared with compliance project)
- David Park: 100%
- Emily Jones: 50% (documentation sprint for v3.1 release notes)
''',
    },
    {
        'filename': 'priority_rules_guide.txt',
        'file_type': 'txt',
        'description': 'How AI priority classification should work for this team',
        'extracted_text': '''Priority Classification Guide for AI Processing

The AI should use these rules when classifying email action items:

HIGH PRIORITY (respond within 2 business days):
- Production incidents or outages
- Security vulnerabilities or CVE notices
- Client escalations from client-corp.com
- Anything marked URGENT in subject line
- Regulatory compliance deadlines
- Items blocking the current sprint

MEDIUM PRIORITY (respond within 5 business days):
- Feature requests with sprint deadline
- Code review requests
- Meeting action items from sprint ceremonies
- Documentation updates for upcoming release
- Performance test planning

LOW PRIORITY (respond within 10 business days):
- Informational vendor notices
- Internal process improvement suggestions
- Non-blocking technical debt items
- Training or knowledge sharing requests
- Long-term planning items

CATEGORY MAPPING:
- 'security' — vulnerabilities, audits, compliance, penetration testing
- 'deployment' — releases, infrastructure, CI/CD, environment setup
- 'client' — client requests, escalations, demos, feedback
- 'development' — features, bug fixes, code reviews, technical design
- 'operations' — monitoring, maintenance, capacity planning, incident response
- 'documentation' — specs, runbooks, release notes, API docs
''',
    },
]

with get_session() as s:
    existing = {d.filename for d in s.query(KnowledgeDocument).all()}
    added = 0
    for doc in docs:
        if doc['filename'] not in existing:
            s.add(KnowledgeDocument(
                filename=doc['filename'],
                file_type=doc['file_type'],
                file_size=len(doc['extracted_text']),
                description=doc['description'],
                extracted_text=doc['extracted_text'],
                extraction_status='success',
            ))
            added += 1
    s.commit()
    print(f'Knowledge base: {added} docs added, {len(existing)} already existed')
\""

# ── 4. Process emails with AI ─────────────────────────────────────────────
echo ""
echo "--- Processing emails with AI ---"
ssh_cmd "sudo podman exec intellibox intellibox process"

# ── 5. Summary ────────────────────────────────────────────────────────────
echo ""
echo "=== Seed complete ==="
echo "Visit https://intellibox-pilot.duckdns.org to see the data."
echo ""
echo "What was created:"
echo "  - 6 roster members (for action assignment)"
echo "  - 3 knowledge base documents (team SOPs, project context, priority rules)"
echo "  - Sample emails copied and processed with AI"
