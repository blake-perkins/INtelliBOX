"""SMTP email sending for reports."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict

from jinja2 import Environment, FileSystemLoader

from intellibox.config import settings
from intellibox.utils.logging import logger


def render_template(template_name: str, context: Dict) -> str:
    """
    Render a Jinja2 template with given context.

    Args:
        template_name: Name of template file
        context: Dictionary of template variables

    Returns:
        Rendered template string
    """
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template(template_name)
    return template.render(**context)


def send_report_email(report_data: Dict, dry_run: bool = False) -> bool:
    """
    Send daily report email via SMTP.

    Args:
        report_data: Report data dictionary from generator
        dry_run: If True, don't actually send email (just log)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Render templates
        html_body = render_template("daily_report.html", report_data)
        text_body = render_template("daily_report.txt", report_data)

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"INtelliBOX Daily Report - {report_data['total_actions']} Unassigned Actions"
        msg["From"] = settings.report_from
        msg["To"] = ", ".join(settings.get_recipients_list())

        # Attach parts (plain text first, then HTML as fallback)
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)

        if dry_run:
            logger.info("DRY RUN: Email not sent")
            logger.info(f"Subject: {msg['Subject']}")
            logger.info(f"To: {msg['To']}")
            logger.info(f"Body preview:\n{text_body[:500]}")
            return True

        # Send email
        logger.info(f"Sending report email to {msg['To']}")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()

            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info("Report email sent successfully")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed - check credentials")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send report email: {e}")
        return False


def preview_report(report_data: Dict) -> str:
    """
    Generate preview of report without sending.

    Args:
        report_data: Report data dictionary

    Returns:
        Rendered plain text report
    """
    return render_template("daily_report.txt", report_data)
