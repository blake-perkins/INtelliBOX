"""Compare AI action extraction: baseline (no KB) vs context-aware (with KB docs).

This script:
1. Captures the current actions as baseline
2. Resets the database
3. Re-inserts KB documents with embeddings
4. Re-ingests all archived emails
5. Runs AI processing WITH KB context in the system prompt
6. Compares baseline vs context-aware actions
7. Generates a detailed report

Usage:
    ./venv/Scripts/python.exe scripts/testing/compare_kb_context.py
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on the path
project_root = Path(__file__).resolve().parent.parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root / "src"))


def capture_actions(label: str) -> dict:
    """Capture all actions grouped by email from the current database."""
    from intellibox.database import get_session
    from intellibox.models import Action, Email

    emails_data = {}
    with get_session() as session:
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
    print(f"  [{label}] Captured {sum(len(e['actions']) for e in emails_data.values())} actions across {len(emails_data)} emails")
    return emails_data


def capture_kb_docs() -> list:
    """Extract KB document data from current database for re-insertion."""
    from intellibox.database import get_session
    from intellibox.models import KnowledgeDocument

    docs = []
    with get_session() as session:
        for doc in session.query(KnowledgeDocument).all():
            docs.append({
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "extracted_text": doc.extracted_text,
                "extraction_status": doc.extraction_status,
                "description": doc.description,
            })
    print(f"  Captured {len(docs)} KB documents")
    return docs


def reset_database():
    """Drop and recreate all database tables."""
    from intellibox.database import drop_db, init_db
    drop_db()
    init_db()
    print("  Database reset complete")


def insert_kb_docs(kb_docs: list):
    """Re-insert KB documents and compute embeddings."""
    from intellibox.database import get_session
    from intellibox.knowledge.embeddings import embed_document
    from intellibox.models import KnowledgeDocument

    for doc_data in kb_docs:
        with get_session() as session:
            doc = KnowledgeDocument(
                filename=doc_data["filename"],
                file_type=doc_data["file_type"],
                file_size=doc_data["file_size"],
                extracted_text=doc_data["extracted_text"],
                extraction_status=doc_data["extraction_status"],
                description=doc_data["description"],
            )
            session.add(doc)
            session.flush()
            doc_id = doc.id

        # Compute embeddings (outside the session that created the doc)
        chunk_count = embed_document(doc_id)
        print(f"  Inserted '{doc_data['filename']}' (doc_id={doc_id}, {chunk_count} chunks embedded)")


def copy_emails_to_inbox() -> int:
    """Copy archived emails back to inbox for re-processing."""
    inbox = Path("data/inbox")
    emails_dir = Path("data/emails")
    inbox.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in emails_dir.iterdir():
        if f.suffix.lower() in (".eml", ".msg") and f.name != ".gitkeep":
            shutil.copy2(f, inbox / f.name)
            count += 1
    print(f"  Copied {count} email files to inbox")
    return count


def ingest_and_process():
    """Run email ingestion and AI processing."""
    from intellibox.database import get_session
    from intellibox.ingestion.parser import process_inbox
    from intellibox.ai.processor import process_unprocessed_emails

    with get_session() as session:
        email_count = process_inbox(session, Path("data/inbox"))
    print(f"  Ingested {email_count} emails")

    with get_session() as session:
        emails_processed, actions_created = process_unprocessed_emails(session)
    print(f"  AI processed {emails_processed} emails -> {actions_created} actions")
    return emails_processed, actions_created


def generate_report(baseline: dict, context_aware: dict) -> str:
    """Generate a markdown comparison report."""
    lines = []
    lines.append("# KB Context Comparison Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # --- Summary Statistics ---
    baseline_total = sum(len(e["actions"]) for e in baseline.values())
    context_total = sum(len(e["actions"]) for e in context_aware.values())

    def priority_dist(data):
        counts = {"high": 0, "medium": 0, "low": 0}
        for e in data.values():
            for a in e["actions"]:
                p = a["priority"] or "medium"
                if p in counts:
                    counts[p] += 1
        return counts

    def category_dist(data):
        counts = {}
        for e in data.values():
            for a in e["actions"]:
                cat = a["category"] or "uncategorized"
                counts[cat] = counts.get(cat, 0) + 1
        return counts

    def avg_confidence(data):
        scores = []
        for e in data.values():
            for a in e["actions"]:
                if a["confidence"] is not None:
                    scores.append(a["confidence"])
        return sum(scores) / len(scores) if scores else 0

    base_pri = priority_dist(baseline)
    ctx_pri = priority_dist(context_aware)
    base_cat = category_dist(baseline)
    ctx_cat = category_dist(context_aware)
    base_conf = avg_confidence(baseline)
    ctx_conf = avg_confidence(context_aware)

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Baseline (no KB) | Context-Aware (with KB) | Delta |")
    lines.append("|--------|-----------------|------------------------|-------|")
    lines.append(f"| Total Actions | {baseline_total} | {context_total} | {context_total - baseline_total:+d} |")
    lines.append(f"| Avg Confidence | {base_conf:.2f} | {ctx_conf:.2f} | {ctx_conf - base_conf:+.2f} |")
    lines.append(f"| High Priority | {base_pri['high']} | {ctx_pri['high']} | {ctx_pri['high'] - base_pri['high']:+d} |")
    lines.append(f"| Medium Priority | {base_pri['medium']} | {ctx_pri['medium']} | {ctx_pri['medium'] - base_pri['medium']:+d} |")
    lines.append(f"| Low Priority | {base_pri['low']} | {ctx_pri['low']} | {ctx_pri['low'] - base_pri['low']:+d} |")
    lines.append("")

    # Category comparison
    all_cats = sorted(set(list(base_cat.keys()) + list(ctx_cat.keys())))
    lines.append("### Category Distribution")
    lines.append("")
    lines.append("| Category | Baseline | Context-Aware | Delta |")
    lines.append("|----------|----------|---------------|-------|")
    for cat in all_cats:
        b = base_cat.get(cat, 0)
        c = ctx_cat.get(cat, 0)
        lines.append(f"| {cat} | {b} | {c} | {c - b:+d} |")
    lines.append("")

    # --- Per-Email Comparison ---
    lines.append("## Per-Email Comparison")
    lines.append("")

    # Get all message IDs from both sets
    all_message_ids = sorted(
        set(list(baseline.keys()) + list(context_aware.keys())),
        key=lambda mid: baseline.get(mid, context_aware.get(mid, {})).get("received_date", ""),
    )

    emails_with_changes = 0

    for msg_id in all_message_ids:
        base_email = baseline.get(msg_id, {})
        ctx_email = context_aware.get(msg_id, {})

        subject = base_email.get("subject") or ctx_email.get("subject", "Unknown")
        sender = base_email.get("from_address") or ctx_email.get("from_address", "Unknown")
        date = base_email.get("received_date") or ctx_email.get("received_date", "")

        base_actions = base_email.get("actions", [])
        ctx_actions = ctx_email.get("actions", [])

        # Detect any changes
        changed = len(base_actions) != len(ctx_actions)
        if not changed:
            for ba, ca in zip(base_actions, ctx_actions):
                if ba["title"] != ca["title"] or ba["priority"] != ca["priority"] or ba["category"] != ca["category"]:
                    changed = True
                    break

        if changed:
            emails_with_changes += 1

        change_marker = " **CHANGED**" if changed else ""
        lines.append(f"### {subject}{change_marker}")
        lines.append(f"**From:** {sender} | **Date:** {date}")
        lines.append(f"**Actions:** {len(base_actions)} baseline -> {len(ctx_actions)} context-aware")
        lines.append("")

        # Show baseline actions
        if base_actions:
            lines.append("**Baseline Actions:**")
            for i, a in enumerate(base_actions, 1):
                due = f" | Due: {a['due_date']}" if a["due_date"] else ""
                conf = f" | Conf: {a['confidence']:.2f}" if a["confidence"] is not None else ""
                lines.append(f"  {i}. **{a['title']}** [{a['priority']}] [{a['category']}]{conf}{due}")
                if a["description"]:
                    lines.append(f"     _{a['description'][:200]}_")
        else:
            lines.append("**Baseline Actions:** _(none)_")

        lines.append("")

        # Show context-aware actions
        if ctx_actions:
            lines.append("**Context-Aware Actions:**")
            for i, a in enumerate(ctx_actions, 1):
                due = f" | Due: {a['due_date']}" if a["due_date"] else ""
                conf = f" | Conf: {a['confidence']:.2f}" if a["confidence"] is not None else ""
                lines.append(f"  {i}. **{a['title']}** [{a['priority']}] [{a['category']}]{conf}{due}")
                if a["description"]:
                    lines.append(f"     _{a['description'][:200]}_")
        else:
            lines.append("**Context-Aware Actions:** _(none)_")

        lines.append("")
        lines.append("---")
        lines.append("")

    # Final summary
    lines.append("## Change Summary")
    lines.append("")
    lines.append(f"- **Emails with changes:** {emails_with_changes} / {len(all_message_ids)}")
    lines.append(f"- **Total actions:** {baseline_total} -> {context_total} ({context_total - baseline_total:+d})")
    lines.append(f"- **Avg confidence:** {base_conf:.2f} -> {ctx_conf:.2f} ({ctx_conf - base_conf:+.2f})")
    lines.append("")

    return "\n".join(lines)


def main():
    print("=" * 70)
    print("KB Context Comparison: Baseline vs Context-Aware Actions")
    print("=" * 70)

    # Step 1: Capture baseline
    print("\n[Step 1] Capturing baseline actions from current database...")
    baseline = capture_actions("Baseline")

    # Step 1b: Capture KB docs for re-insertion
    print("\n[Step 1b] Capturing KB document texts...")
    kb_docs = capture_kb_docs()
    if not kb_docs:
        print("  WARNING: No KB documents found. The comparison will show no difference.")
        print("  Upload documents at /knowledge-base first, then re-run.")
        sys.exit(1)

    # Step 2: Backup and reset database
    print("\n[Step 2] Backing up and resetting database...")
    db_path = Path("data/intellibox.db")
    backup_path = Path("data/intellibox.db.backup")
    if db_path.exists():
        shutil.copy2(db_path, backup_path)
        print(f"  Backup saved to {backup_path}")
    reset_database()

    # Step 3: Re-insert KB documents
    print("\n[Step 3] Re-inserting KB documents with embeddings...")
    insert_kb_docs(kb_docs)

    # Step 4: Copy emails to inbox
    print("\n[Step 4] Copying archived emails to inbox...")
    copy_emails_to_inbox()

    # Step 5: Ingest and process with AI
    print("\n[Step 5] Ingesting emails and running AI processing (this takes a minute)...")
    ingest_and_process()

    # Step 6: Capture context-aware actions
    print("\n[Step 6] Capturing context-aware actions...")
    context_aware = capture_actions("Context-Aware")

    # Step 7: Generate report
    print("\n[Step 7] Generating comparison report...")
    report = generate_report(baseline, context_aware)

    # Save report
    report_path = Path("data/kb_comparison_report.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"  Report saved to {report_path}")

    # Print report to stdout
    print("\n" + "=" * 70)
    print(report)

    print("\n" + "=" * 70)
    print(f"Done. Database backup at: {backup_path}")
    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()
