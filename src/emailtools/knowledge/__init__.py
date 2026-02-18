"""Knowledge base package — document storage and RAG context."""

from emailtools.database import get_session
from emailtools.models import KnowledgeDocument

# Max characters of KB text to inject into AI prompts
MAX_CONTEXT_CHARS = 30_000


def get_knowledge_context() -> str:
    """Build a knowledge base context string for AI prompt injection.

    Queries all successfully-extracted documents, concatenates their text
    with document headers, and truncates to MAX_CONTEXT_CHARS.

    Returns:
        Formatted context string, or empty string if no documents.
    """
    with get_session() as session:
        docs = (
            session.query(KnowledgeDocument)
            .filter(KnowledgeDocument.extraction_status == "success")
            .filter(KnowledgeDocument.extracted_text.isnot(None))
            .order_by(KnowledgeDocument.uploaded_at.desc())
            .all()
        )

        if not docs:
            return ""

        sections = []
        total_chars = 0

        for doc in docs:
            header = f"--- {doc.filename}"
            if doc.description:
                header += f" ({doc.description})"
            header += " ---"

            text = doc.extracted_text.strip()
            remaining = MAX_CONTEXT_CHARS - total_chars - len(header) - 4  # 4 for newlines
            if remaining <= 0:
                break

            if len(text) > remaining:
                text = text[:remaining] + "...[truncated]"

            sections.append(f"{header}\n{text}")
            total_chars += len(header) + len(text) + 2

        context = "\n\n".join(sections)

    return context
