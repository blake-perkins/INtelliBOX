"""Parser for Outlook .msg files."""

import extract_msg
from datetime import datetime

from emailtools.utils.datetime_utils import utcnow
from pathlib import Path
from typing import Tuple, Optional, List

from emailtools.utils.logging import logger


def parse_msg_file(msg_path: Path) -> Tuple[str, str, str, str, List[str], List[str], datetime, Optional[str], Optional[str]]:
    """
    Parse an Outlook .msg file and extract email data.

    Args:
        msg_path: Path to the .msg file

    Returns:
        Tuple of (message_id, subject, from_name, from_address, to_addresses,
                 cc_addresses, received_date, body_text, body_html)

    Raises:
        ValueError: If the file cannot be parsed
    """
    try:
        msg = extract_msg.Message(str(msg_path))

        # Extract message ID (generate if not present)
        message_id = msg.messageId or f"<{msg_path.stem}@outlook.local>"

        # Extract subject
        subject = msg.subject or "(No Subject)"

        # Extract sender
        from_name = msg.sender or ""
        # PidTagSenderEmailAddress (0x0C1F) — not exposed as a direct attribute
        from_address = msg.getStringStream("__substg1.0_0C1F") or "unknown@unknown.com"

        # Extract recipients
        to_addresses = []
        if msg.to:
            # Parse "Name <email>" format
            for recipient in msg.to.split(";"):
                recipient = recipient.strip()
                if "<" in recipient and ">" in recipient:
                    email = recipient.split("<")[1].split(">")[0]
                    to_addresses.append(email)
                elif "@" in recipient:
                    to_addresses.append(recipient)

        # Extract CC
        cc_addresses = []
        if msg.cc:
            for recipient in msg.cc.split(";"):
                recipient = recipient.strip()
                if "<" in recipient and ">" in recipient:
                    email = recipient.split("<")[1].split(">")[0]
                    cc_addresses.append(email)
                elif "@" in recipient:
                    cc_addresses.append(recipient)

        # Extract date
        if msg.date:
            try:
                received_date = datetime.fromisoformat(str(msg.date))
            except:
                received_date = utcnow()
        else:
            received_date = utcnow()

        # Extract body
        body_text = msg.body or None
        body_html = msg.htmlBody or None

        msg.close()

        logger.debug(f"Parsed .msg file: {subject}")
        return (
            message_id,
            subject,
            from_name,
            from_address,
            to_addresses,
            cc_addresses,
            received_date,
            body_text,
            body_html
        )

    except Exception as e:
        logger.error(f"Failed to parse .msg file {msg_path}: {e}")
        raise ValueError(f"Cannot parse .msg file: {e}")
