"""Knowledge base package — document storage and RAG context."""

import time
from typing import Dict, List

from intellibox.database import get_session
from intellibox.models import KnowledgeDocument
from intellibox.utils.logging import logger

# Max characters of KB text to inject into AI prompts
MAX_CONTEXT_CHARS = 30_000

# TTL cache for get_knowledge_context (avoids repeated DB queries)
_KB_CACHE_TTL = 300  # 5 minutes
_kb_cache: Dict = {"text": None, "expires": 0}


def _invalidate_kb_cache() -> None:
    """Clear the knowledge context cache (used by tests and after uploads)."""
    _kb_cache["text"] = None
    _kb_cache["expires"] = 0


def get_knowledge_context() -> str:
    """Build a knowledge base context string for AI prompt injection.

    Uses a 5-minute TTL cache to avoid repeated database queries.
    Queries all successfully-extracted documents, concatenates their text
    with document headers, and truncates to MAX_CONTEXT_CHARS.

    Returns:
        Formatted context string, or empty string if no documents.
    """
    # Check cache
    if _kb_cache["text"] is not None and time.time() < _kb_cache["expires"]:
        return _kb_cache["text"]

    with get_session() as session:
        docs = (
            session.query(KnowledgeDocument)
            .filter(KnowledgeDocument.extraction_status == "success")
            .filter(KnowledgeDocument.extracted_text.isnot(None))
            .order_by(KnowledgeDocument.uploaded_at.desc())
            .all()
        )

        if not docs:
            _kb_cache["text"] = ""
            _kb_cache["expires"] = time.time() + _KB_CACHE_TTL
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

    _kb_cache["text"] = context
    _kb_cache["expires"] = time.time() + _KB_CACHE_TTL
    return context


def search_knowledge_base(
    sender: str = "",
    title: str = "",
    description: str = "",
    category: str = "",
) -> List[Dict]:
    """Search KB documents for content relevant to an action.

    Uses OpenAI embeddings when available, falls back to TF-IDF similarity.
    Both methods return results ranked by relevance score.

    Args:
        sender: Email address of the action's sender
        title: Action title text
        description: Action description text
        category: Action category name

    Returns:
        List of dicts with: doc_id, doc_filename, snippet, score, method
    """
    # Build a combined query string from all action metadata
    parts = []
    if title:
        parts.append(title)
    if description:
        parts.append(description)
    if category:
        parts.append(category.replace("_", " "))
    if sender:
        parts.append(sender)

    query_text = " ".join(parts)
    if not query_text.strip():
        return []

    from intellibox.knowledge.embeddings import (
        _has_api_key,
        _has_embeddings,
        search_by_embeddings,
        search_by_tfidf,
    )

    # Try embeddings first (requires API key + stored embeddings)
    if _has_api_key() and _has_embeddings():
        results = search_by_embeddings(query_text)
        if results:
            logger.debug(f"KB search: {len(results)} results via embeddings")
            return results
        # If embeddings returned nothing, fall through to TF-IDF

    # Fallback: TF-IDF similarity (always available, no API key needed)
    results = search_by_tfidf(query_text)
    logger.debug(f"KB search: {len(results)} results via TF-IDF")
    return results
