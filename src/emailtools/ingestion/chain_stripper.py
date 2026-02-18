"""Strip quoted and forwarded content from email bodies."""

import re

# Patterns that indicate the start of quoted/forwarded content.
# Everything from the first match onward is removed.
_QUOTE_PATTERNS = [
    # "On Mon, Jan 1, 2026 at 10:00 AM John Doe <john@example.com> wrote:"
    re.compile(r"^On .+wrote:\s*$", re.MULTILINE | re.IGNORECASE),
    # Outlook: "-----Original Message-----"
    re.compile(r"^-{3,}\s*Original Message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    # Outlook: "________" horizontal rule before forwarded content
    re.compile(r"^_{5,}\s*$", re.MULTILINE),
    # Outlook forwarded header block: "From: ... Sent: ... To: ... Subject: ..."
    re.compile(
        r"^From:\s*.+\n\s*Sent:\s*.+\n\s*To:\s*.+\n\s*Subject:\s*.+",
        re.MULTILINE | re.IGNORECASE,
    ),
    # "---------- Forwarded message ----------"
    re.compile(r"^-{3,}\s*Forwarded message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
]


def strip_quoted_text(body: str) -> str:
    """
    Remove quoted and forwarded content from an email body.

    Strips everything after the first recognized quote/forward marker,
    then removes any lines that start with '>' (inline quoting).

    If the result is empty or whitespace-only, returns the original body
    (better to send the full chain than nothing).

    Args:
        body: The raw email body text.

    Returns:
        The cleaned body with only the newest message content.
    """
    if not body:
        return body

    # Find the earliest quote/forward marker and truncate there
    earliest_pos = len(body)
    for pattern in _QUOTE_PATTERNS:
        match = pattern.search(body)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()

    stripped = body[:earliest_pos]

    # Remove inline '>' quoted lines from what remains
    lines = stripped.splitlines()
    lines = [line for line in lines if not line.lstrip().startswith(">")]
    stripped = "\n".join(lines).strip()

    # If stripping removed everything, fall back to original
    if not stripped:
        return body.strip()

    return stripped
