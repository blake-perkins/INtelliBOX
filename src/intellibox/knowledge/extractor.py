"""Text extraction from uploaded documents."""

import io
from typing import Tuple


def extract_text(content: bytes, file_type: str) -> Tuple[str, str]:
    """Extract text from document bytes.

    Args:
        content: Raw file bytes
        file_type: One of 'pdf', 'docx', 'txt', 'md', 'csv', 'json',
                   'html', 'xml', 'rtf', 'log'

    Returns:
        Tuple of (extracted_text, status) where status is
        'success', 'partial', or 'failed'
    """
    try:
        if file_type in ("txt", "md", "csv", "json", "html", "xml", "rtf", "log"):
            return _extract_txt(content)
        elif file_type == "pdf":
            return _extract_pdf(content)
        elif file_type == "docx":
            return _extract_docx(content)
        else:
            return "", "failed"
    except Exception:
        return "", "failed"


def _extract_txt(content: bytes) -> Tuple[str, str]:
    """Extract text from a plain text file."""
    for encoding in ("utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            return text.strip(), "success"
        except UnicodeDecodeError:
            continue
    return "", "failed"


def _extract_pdf(content: bytes) -> Tuple[str, str]:
    """Extract text from a PDF file using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages_text = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages_text.append(page_text)

    if not pages_text:
        return "", "partial"  # Scanned PDF with no selectable text

    text = "\n\n".join(pages_text).strip()

    # Detect garbage extraction from scanned/image PDFs:
    # high ratio of non-alphanumeric chars suggests OCR artifacts or junk
    if text:
        alnum = sum(1 for c in text if c.isalnum() or c.isspace())
        ratio = alnum / len(text) if len(text) > 0 else 0
        if ratio < 0.5:
            return text, "partial"

    return text, "success"


def _extract_docx(content: bytes) -> Tuple[str, str]:
    """Extract text from a Word document using python-docx."""
    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        return "", "partial"

    return "\n\n".join(paragraphs).strip(), "success"
