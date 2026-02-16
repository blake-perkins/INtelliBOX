"""Command-line interface for EmailTools."""

import json
from pathlib import Path
from typing import Optional

import click
from sqlalchemy import func
from tabulate import tabulate

from emailtools.config import settings
from emailtools.database import SessionLocal, get_session, init_db
from emailtools.ingestion.parser import parse_and_store_email, process_inbox
from emailtools.models import Action, Assignment, Email, ProcessingLog
from emailtools.utils.logging import logger


@click.group()
def cli():
    """EmailTools - Email action tracking system."""
    pass


@cli.command()
def init():
    """Initialize the database and create all tables."""
    try:
        init_db()
        click.echo("[OK] Database initialized successfully")
        click.echo(f"  Location: data/emailtools.db")
    except Exception as e:
        click.echo(f"[ERROR] Failed to initialize database: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--watch",
    is_flag=True,
    help="Continuously watch inbox for new emails"
)
@click.option(
    "--interval",
    default=5,
    help="Watch interval in seconds (default: 5)"
)
def process(watch: bool, interval: int):
    """Process emails from the inbox directory."""
    inbox_dir = Path("data/inbox")

    if watch:
        from emailtools.ingestion.file_watcher import watch_inbox

        def callback(eml_path: Path):
            with get_session() as session:
                parse_and_store_email(eml_path, session)

        click.echo(f"Watching inbox: {inbox_dir}")
        click.echo("Press Ctrl+C to stop")
        watch_inbox(inbox_dir, callback, interval=interval, run_once=False)
    else:
        with get_session() as session:
            count = process_inbox(session, inbox_dir)
            if count > 0:
                click.echo(f"[OK] Processed {count} email(s)")
            else:
                click.echo("No new emails to process")


@cli.group()
def db():
    """Database management commands."""
    pass


@db.command(name="show")
@click.option(
    "--table",
    type=click.Choice(["emails", "actions", "assignments", "logs"], case_sensitive=False),
    help="Show specific table (default: summary)"
)
@click.option(
    "--limit",
    default=10,
    help="Number of records to show (default: 10)"
)
def db_show(table: Optional[str], limit: int):
    """Display database contents."""
    with get_session() as session:
        if table == "emails":
            _show_emails(session, limit)
        elif table == "actions":
            _show_actions(session, limit)
        elif table == "assignments":
            _show_assignments(session, limit)
        elif table == "logs":
            _show_logs(session, limit)
        else:
            _show_summary(session)


def _show_summary(session):
    """Show database summary."""
    email_count = session.query(func.count(Email.id)).scalar()
    action_count = session.query(func.count(Action.id)).scalar()
    assignment_count = session.query(func.count(Assignment.id)).scalar()
    log_count = session.query(func.count(ProcessingLog.id)).scalar()

    processed_count = session.query(func.count(Email.id)).filter(Email.processed == True).scalar()
    unprocessed_count = email_count - processed_count

    click.echo("\n=== Database Summary")
    click.echo("=" * 50)
    click.echo(f"  Emails:       {email_count:>6} ({processed_count} processed, {unprocessed_count} pending)")
    click.echo(f"  Actions:      {action_count:>6}")
    click.echo(f"  Assignments:  {assignment_count:>6}")
    click.echo(f"  Logs:         {log_count:>6}")
    click.echo("=" * 50 + "\n")


def _show_emails(session, limit: int):
    """Show emails table."""
    emails = session.query(Email).order_by(Email.created_at.desc()).limit(limit).all()

    if not emails:
        click.echo("No emails found")
        return

    rows = []
    for email in emails:
        rows.append([
            email.id,
            email.subject[:40] + "..." if len(email.subject) > 40 else email.subject,
            email.from_address,
            email.received_date.strftime("%Y-%m-%d %H:%M"),
            "[OK]" if email.processed else "[X]",
            len(email.actions)
        ])

    headers = ["ID", "Subject", "From", "Received", "Processed", "Actions"]
    click.echo(f"\nEMAILS: Emails (showing {len(emails)}/{limit})")
    click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
    click.echo()


def _show_actions(session, limit: int):
    """Show actions table."""
    actions = session.query(Action).order_by(Action.created_at.desc()).limit(limit).all()

    if not actions:
        click.echo("No actions found")
        return

    rows = []
    for action in actions:
        rows.append([
            action.id,
            action.title[:40] + "..." if len(action.title) > 40 else action.title,
            action.priority or "-",
            action.due_date.strftime("%Y-%m-%d") if action.due_date else "-",
            f"{action.confidence_score:.2f}" if action.confidence_score else "-",
            "[OK]" if action.is_assigned else "[X]"
        ])

    headers = ["ID", "Title", "Priority", "Due Date", "Confidence", "Assigned"]
    click.echo(f"\nACTIONS: Actions (showing {len(actions)}/{limit})")
    click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
    click.echo()


def _show_assignments(session, limit: int):
    """Show assignments table."""
    assignments = session.query(Assignment).order_by(Assignment.assigned_at.desc()).limit(limit).all()

    if not assignments:
        click.echo("No assignments found")
        return

    rows = []
    for assignment in assignments:
        rows.append([
            assignment.id,
            assignment.action_id,
            assignment.assigned_to or "-",
            assignment.status,
            assignment.assigned_at.strftime("%Y-%m-%d %H:%M")
        ])

    headers = ["ID", "Action ID", "Assigned To", "Status", "Assigned At"]
    click.echo(f"\nASSIGNMENTS: Assignments (showing {len(assignments)}/{limit})")
    click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
    click.echo()


def _show_logs(session, limit: int):
    """Show processing logs."""
    logs = session.query(ProcessingLog).order_by(ProcessingLog.created_at.desc()).limit(limit).all()

    if not logs:
        click.echo("No logs found")
        return

    rows = []
    for log in logs:
        status_icon = {"success": "[OK]", "failure": "[X]", "warning": "[!]"}.get(log.status, "?")
        rows.append([
            log.id,
            log.event_type,
            f"{status_icon} {log.status}",
            log.message[:50] + "..." if log.message and len(log.message) > 50 else (log.message or "-"),
            log.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    headers = ["ID", "Event", "Status", "Message", "Timestamp"]
    click.echo(f"\nLOGS: Processing Logs (showing {len(logs)}/{limit})")
    click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
    click.echo()


@cli.group()
def actions():
    """Action management commands."""
    pass


@actions.command(name="list")
@click.option(
    "--unassigned",
    is_flag=True,
    help="Show only unassigned actions"
)
@click.option(
    "--priority",
    type=click.Choice(["high", "medium", "low"], case_sensitive=False),
    help="Filter by priority"
)
@click.option(
    "--limit",
    default=20,
    help="Number of actions to show (default: 20)"
)
def actions_list(unassigned: bool, priority: Optional[str], limit: int):
    """List actions."""
    with get_session() as session:
        query = session.query(Action).join(Email)

        # Apply filters
        if unassigned:
            query = query.filter(~Action.assignments.any())

        if priority:
            query = query.filter(Action.priority == priority.lower())

        actions_list_result = query.order_by(Action.created_at.desc()).limit(limit).all()

        if not actions_list_result:
            click.echo("No actions found")
            return

        click.echo(f"\nACTIONS: Found {len(actions_list_result)} action(s)\n")

        for action in actions_list_result:
            priority_icon = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]"}.get(
                action.priority, "[-]"
            )
            assigned_icon = "[OK]" if action.is_assigned else "[X]"

            click.echo(f"{priority_icon} Action #{action.id}: {action.title}")
            click.echo(f"   From: {action.email.from_address} - {action.email.subject[:50]}")
            click.echo(f"   Priority: {action.priority or 'None'} | Assigned: {assigned_icon}")
            if action.due_date:
                click.echo(f"   Due: {action.due_date.strftime('%Y-%m-%d')}")
            if action.description:
                desc = action.description[:100] + "..." if len(action.description) > 100 else action.description
                click.echo(f"   Description: {desc}")
            click.echo()


@cli.group()
def ai():
    """AI processing commands."""
    pass


@ai.command(name="parse")
@click.option(
    "--email-id",
    type=int,
    help="Specific email ID to parse (optional)"
)
@click.option(
    "--all",
    "parse_all",
    is_flag=True,
    help="Parse all unprocessed emails"
)
@click.option(
    "--limit",
    type=int,
    help="Limit number of emails to process"
)
def ai_parse(email_id: Optional[int], parse_all: bool, limit: Optional[int]):
    """Parse emails with AI to extract actions."""
    from emailtools.ai.processor import process_email_with_ai, process_unprocessed_emails

    with get_session() as session:
        if email_id:
            # Parse specific email
            email = session.query(Email).filter_by(id=email_id).first()
            if not email:
                click.echo(f"[ERROR] Email ID {email_id} not found", err=True)
                return

            click.echo(f"Processing email ID {email_id} with AI...")
            actions_count = process_email_with_ai(email, session)
            click.echo(f"[OK] Extracted {actions_count} action(s)")

        elif parse_all or limit:
            # Parse all or limited unprocessed emails
            emails_processed, total_actions = process_unprocessed_emails(session, limit=limit)
            if emails_processed > 0:
                click.echo(f"[OK] Processed {emails_processed} email(s), extracted {total_actions} action(s)")
            else:
                click.echo("No unprocessed emails found")

        else:
            click.echo("[ERROR] Specify --email-id <ID>, --all, or --limit <N>", err=True)


@cli.group()
def report():
    """Report generation commands."""
    pass


@report.command(name="generate")
@click.option(
    "--preview",
    is_flag=True,
    help="Show preview without sending email"
)
def report_generate(preview: bool):
    """Generate daily report."""
    from emailtools.reporter.generator import generate_report_data
    from emailtools.reporter.email_sender import preview_report

    with get_session() as session:
        click.echo("Generating report...")
        report_data = generate_report_data(session)

        if preview:
            # Show preview
            preview_text = preview_report(report_data)
            click.echo("\n" + "=" * 80)
            click.echo(preview_text)
            click.echo("=" * 80 + "\n")
        else:
            click.echo(f"[OK] Report generated: {report_data['total_actions']} unassigned actions")
            click.echo(f"  High: {report_data['high_priority_count']}, "
                      f"Medium: {report_data['medium_priority_count']}, "
                      f"Low: {report_data['low_priority_count']}")


@report.command(name="send")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview email without actually sending"
)
def report_send(dry_run: bool):
    """Generate and send daily report email."""
    from emailtools.reporter.generator import generate_report_data
    from emailtools.reporter.email_sender import send_report_email

    with get_session() as session:
        click.echo("Generating report...")
        report_data = generate_report_data(session)

        click.echo(f"Report: {report_data['total_actions']} unassigned actions")

        if dry_run:
            click.echo("\n[DRY RUN] Email preview (not sending):")
            success = send_report_email(report_data, dry_run=True)
        else:
            click.echo("Sending email...")
            success = send_report_email(report_data, dry_run=False)

        if success:
            click.echo("[OK] Report email sent successfully" if not dry_run else "[OK] Preview complete")
        else:
            click.echo("[ERROR] Failed to send report email", err=True)


@report.command(name="schedule")
def report_schedule():
    """Start scheduler for nightly reports (runs in foreground)."""
    from emailtools.reporter.scheduler import start_scheduler

    click.echo(f"Starting report scheduler...")
    click.echo(f"Reports will be sent daily at {settings.report_time}")
    click.echo("Press Ctrl+C to stop\n")

    start_scheduler()


@cli.command(name="web")
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind to"
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="Port to bind to"
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development"
)
def web(host: str, port: int, reload: bool):
    """Start the web interface server."""
    import uvicorn
    from emailtools.web.app import app

    click.echo(f"Starting EmailTools web interface...")
    click.echo(f"  URL: http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
    click.echo(f"  Press Ctrl+C to stop")

    uvicorn.run(
        "emailtools.web.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    cli()
