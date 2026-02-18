"""Email parsing module for extracting data from .eml files."""

import email
import json
import shutil
from datetime import datetime

from emailtools.utils.datetime_utils import utcnow
from email import policy
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from emailtools.models import Email, ProcessingLog
from emailtools.utils.logging import logger


def parse_eml_file(eml_path: Path) -> EmailMessage:
    """
    Parse an .eml file and return an EmailMessage object.

    Args:
        eml_path: Path to the .eml file

    Returns:
        Parsed EmailMessage object

    Raises:
        FileNotFoundError: If the .eml file doesn't exist
        ValueError: If the file cannot be parsed
    """
    if not eml_path.exists():
        raise FileNotFoundError(f"Email file not found: {eml_path}")

    try:
        with open(eml_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
        return msg
    except Exception as e:
        logger.error(f"Failed to parse .eml file {eml_path}: {e}")
        raise ValueError(f"Cannot parse email file: {e}")


def extract_email_addresses(header_value: Optional[str]) -> List[str]:
    """
    Extract email addresses from a header value.

    Args:
        header_value: Raw header value (e.g., "John Doe <john@example.com>, jane@example.com")

    Returns:
        List of email addresses
    """
    if not header_value:
        return []

    addresses = []
    for part in header_value.split(","):
        name, addr = parseaddr(part.strip())
        if addr:
            addresses.append(addr)
    return addresses


def extract_body_text(msg: EmailMessage) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract plain text and HTML body from email message.

    Args:
        msg: Parsed EmailMessage object

    Returns:
        Tuple of (plain_text, html_text)
    """
    plain_text = None
    html_text = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and plain_text is None:
                try:
                    plain_text = part.get_content()
                except Exception as e:
                    logger.warning(f"Failed to extract plain text: {e}")

            elif content_type == "text/html" and html_text is None:
                try:
                    html_text = part.get_content()
                except Exception as e:
                    logger.warning(f"Failed to extract HTML: {e}")
    else:
        # Non-multipart message
        content_type = msg.get_content_type()
        try:
            content = msg.get_content()
            if content_type == "text/plain":
                plain_text = content
            elif content_type == "text/html":
                html_text = content
        except Exception as e:
            logger.warning(f"Failed to extract body: {e}")

    return plain_text, html_text


def archive_eml_file(email_path: Path, message_id: str) -> str:
    """
    Move email file from inbox to archive directory.

    Args:
        email_path: Current path of the email file (.eml or .msg)
        message_id: Email message ID (used for filename)

    Returns:
        Path to archived file
    """
    # Create safe filename from message_id
    safe_filename = message_id.replace("<", "").replace(">", "").replace("/", "_")
    archive_dir = Path("data/emails")
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Preserve original file extension
    file_extension = email_path.suffix
    archive_path = archive_dir / f"{safe_filename}{file_extension}"

    # Handle duplicate filenames
    counter = 1
    while archive_path.exists():
        archive_path = archive_dir / f"{safe_filename}_{counter}{file_extension}"
        counter += 1

    shutil.move(str(email_path), str(archive_path))
    logger.info(f"Archived email to: {archive_path}")

    return str(archive_path)


def parse_and_store_email(email_path: Path, session: Session) -> Optional[Email]:
    """
    Parse an email file (.eml or .msg) and store it in the database.

    Args:
        email_path: Path to the email file
        session: Database session

    Returns:
        Created Email object, or None if parsing failed
    """
    try:
        # Check file extension and parse accordingly
        if email_path.suffix.lower() == ".msg":
            # Parse Outlook .msg file
            from emailtools.ingestion.msg_parser import parse_msg_file

            (message_id, subject, from_name, from_address, to_addresses,
             cc_addresses, received_date, body_text, body_html) = parse_msg_file(email_path)

        elif email_path.suffix.lower() == ".eml":
            # Parse standard .eml file
            msg = parse_eml_file(email_path)

            # Extract message ID
            message_id = msg.get("Message-ID")
            if not message_id:
                logger.warning(f"Email has no Message-ID, generating one: {email_path}")
                message_id = f"<{email_path.stem}@emailtools.local>"

            # Extract header information
            subject = msg.get("Subject", "(No Subject)")
            from_header = msg.get("From", "")
            from_name, from_address = parseaddr(from_header)

            to_addresses = extract_email_addresses(msg.get("To"))
            cc_addresses = extract_email_addresses(msg.get("Cc"))

            # Parse received date
            date_header = msg.get("Date")
            try:
                if date_header:
                    received_date = parsedate_to_datetime(date_header)
                else:
                    received_date = utcnow()
            except Exception as e:
                logger.warning(f"Failed to parse date, using current time: {e}")
                received_date = utcnow()

            # Extract body
            body_text, body_html = extract_body_text(msg)

        else:
            logger.error(f"Unsupported file type: {email_path.suffix}")
            return None

        # Check if email already exists — merge duplicate senders
        existing = session.query(Email).filter_by(message_id=message_id).first()
        if existing:
            also = json.loads(existing.also_received_from or "[]")

            # Determine if the new copy has more substantive content.
            # If so, promote it to primary and demote the old primary.
            new_body_len = len(body_text or "")
            old_body_len = len(existing.body_text or "")

            if new_body_len > old_body_len and from_address != existing.from_address:
                # Demote current primary into also_received_from
                old_sender = {"address": existing.from_address, "name": existing.from_name or ""}
                if not any(s["address"] == existing.from_address for s in also):
                    also.append(old_sender)

                # Promote new email to primary
                existing.from_address = from_address
                existing.from_name = from_name
                existing.subject = subject
                existing.body_text = body_text
                existing.body_html = body_html
                existing.also_received_from = json.dumps(also)
                logger.info(f"Duplicate email promoted — {from_address} has longer body ({new_body_len} > {old_body_len})")
            elif from_address != existing.from_address and not any(s["address"] == from_address for s in also):
                # New sender but shorter body — just add to also_received_from
                also.append({"address": from_address, "name": from_name})
                existing.also_received_from = json.dumps(also)
                logger.info(f"Duplicate email merged — added sender {from_address}")
            else:
                logger.info(f"Duplicate email from same sender, skipped: {message_id}")

            log_entry = ProcessingLog(
                email_id=existing.id,
                event_type="email_received",
                status="success",
                message=f"Duplicate merged from {from_address}",
                event_metadata=json.dumps({"file_path": str(email_path), "sender": from_address})
            )
            session.add(log_entry)
            session.commit()
            # Delete duplicate file
            email_path.unlink()
            return None

        # Archive the email file
        archived_path = archive_eml_file(email_path, message_id)

        # Create Email record
        email_record = Email(
            message_id=message_id,
            subject=subject,
            from_address=from_address or "unknown@unknown.com",
            from_name=from_name or None,
            to_addresses=json.dumps(to_addresses),
            cc_addresses=json.dumps(cc_addresses) if cc_addresses else None,
            received_date=received_date,
            body_text=body_text,
            body_html=body_html,
            raw_eml_path=archived_path,
            processed=False
        )

        session.add(email_record)
        session.flush()  # Get the ID

        # Log successful parsing
        log_entry = ProcessingLog(
            email_id=email_record.id,
            event_type="email_received",
            status="success",
            message=f"Email parsed and stored: {subject[:50]}",
            event_metadata=json.dumps({
                "from": from_address,
                "to_count": len(to_addresses),
                "cc_count": len(cc_addresses)
            })
        )
        session.add(log_entry)
        session.commit()

        logger.info(f"Successfully parsed email: {message_id} - {subject[:50]}")
        return email_record

    except Exception as e:
        logger.error(f"Failed to parse and store email {email_path}: {e}")
        session.rollback()

        # Log failure
        log_entry = ProcessingLog(
            email_id=None,
            event_type="email_received",
            status="failure",
            message=f"Failed to parse email: {str(e)}",
            event_metadata=json.dumps({"file_path": str(email_path)})
        )
        session.add(log_entry)
        session.commit()

        return None


def process_inbox(session: Session, inbox_dir: Path = Path("data/inbox")) -> int:
    """
    Process all .eml and .msg files in the inbox directory.

    Args:
        session: Database session
        inbox_dir: Path to inbox directory

    Returns:
        Number of emails successfully processed
    """
    if not inbox_dir.exists():
        inbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created inbox directory: {inbox_dir}")
        return 0

    # Get both .eml and .msg files
    eml_files = list(inbox_dir.glob("*.eml"))
    msg_files = list(inbox_dir.glob("*.msg"))
    all_files = eml_files + msg_files

    if not all_files:
        logger.info("No email files found in inbox")
        return 0

    logger.info(f"Found {len(all_files)} email file(s) to process ({len(eml_files)} .eml, {len(msg_files)} .msg)")

    processed_count = 0
    for email_file in all_files:
        result = parse_and_store_email(email_file, session)
        if result:
            processed_count += 1

    logger.info(f"Processed {processed_count}/{len(all_files)} emails successfully")
    return processed_count
