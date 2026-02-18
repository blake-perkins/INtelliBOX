"""Generate comparison report from backup (baseline) and current (context-aware) databases.

Recovery script: the main compare script crashed on a unicode encoding issue
after all AI processing was complete. This reads both databases and generates the report.

Usage:
    ./venv/Scripts/python.exe scripts/testing/generate_report.py
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root / "src"))


def capture_from_db(db_url: str, label: str) -> dict:
    """Capture all actions grouped by email from a specific database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from emailtools.models import Action, Email

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    session = Session()

    emails_data = {}
    try:
        emails = session.query(Email).order_by(Email.received_date).all()
        for email in emails:
            actions = (
                session.query(Action)
                .filter_by(email_id=email.id)
                .order_by(Action.id)
                .all()
            )
            emails_data[email.message_id] = {
                "subject": email.subject,
                "from_address": email.from_address,
                "received_date": str(email.received_date),
                "actions": [
                    {
                        "title": a.title,
                        "description": a.description or "",
                        "priority": a.priority,
                        "category": a.category or "",
                        "confidence": a.confidence_score,
                        "due_date": str(a.due_date.date()) if a.due_date else None,
                    }
                    for a in actions
                ],
            }
    finally:
        session.close()
        engine.dispose()

    total = sum(len(e["actions"]) for e in emails_data.values())
    print(f"  [{label}] {total} actions across {len(emails_data)} emails")
    return emails_data


def main():
    # Import the report generator from the main script
    sys.path.insert(0, str(Path(__file__).parent))
    from compare_kb_context import generate_report

    backup_db = Path("data/emailtools.db.backup")
    current_db = Path("data/emailtools.db")

    if not backup_db.exists():
        print("ERROR: Backup database not found at data/emailtools.db.backup")
        sys.exit(1)

    print("Reading baseline from backup database...")
    baseline = capture_from_db(f"sqlite:///{backup_db}", "Baseline")

    print("Reading context-aware from current database...")
    context_aware = capture_from_db(f"sqlite:///{current_db}", "Context-Aware")

    print("Generating report...")
    report = generate_report(baseline, context_aware)

    report_path = Path("data/kb_comparison_report.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"Report saved to {report_path}")

    # Print to stdout (use ascii-safe output)
    for line in report.split("\n"):
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()
