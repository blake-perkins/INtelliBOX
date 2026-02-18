"""Scheduler for automated nightly reports."""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from intellibox.config import settings
from intellibox.database import get_session
from intellibox.reporter.email_sender import send_report_email
from intellibox.reporter.generator import generate_report_data
from intellibox.utils.logging import logger


def send_daily_report():
    """
    Generate and send the daily report.
    Called by scheduler at configured time.
    """
    logger.info("Starting scheduled daily report generation")

    try:
        with get_session() as session:
            # Generate report data
            report_data = generate_report_data(session)

            # Send email
            success = send_report_email(report_data, dry_run=False)

            if success:
                logger.info("Daily report sent successfully")
            else:
                logger.error("Failed to send daily report")

    except Exception as e:
        logger.error(f"Error in scheduled report generation: {e}")


def start_scheduler():
    """
    Start the scheduler for nightly reports.
    Runs in foreground (blocking).
    """
    scheduler = BlockingScheduler()

    # Parse report time (HH:MM format)
    hour, minute = map(int, settings.report_time.split(":"))

    # Schedule daily report
    trigger = CronTrigger(
        hour=hour,
        minute=minute,
        timezone=settings.timezone
    )

    scheduler.add_job(
        send_daily_report,
        trigger=trigger,
        id="daily_report",
        name="Daily INtelliBOX Report"
    )

    logger.info(
        f"Scheduler started - Reports will be sent daily at {settings.report_time} "
        f"({settings.timezone})"
    )
    logger.info("Press Ctrl+C to stop")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
