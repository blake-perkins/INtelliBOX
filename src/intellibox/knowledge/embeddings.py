"""Semantic search for knowledge base — OpenAI embeddings with TF-IDF fallback."""

import json
import math
from typing import Dict, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from intellibox.database import get_session
from intellibox.models import KnowledgeChunk, KnowledgeDocument
from intellibox.utils.logging import logger

# --- Chunking ----------------------------------------------------------------

CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 100  # overlap between consecutive chunks


def chunk_text(text: str) -> List[str]:
    """Split document text into overlapping chunks.

    Uses paragraph boundaries when possible, falls back to character windows.
    Returns chunks of roughly CHUNK_SIZE characters with CHUNK_OVERLAP overlap.
    """
    if not text or not text.strip():
        return []

    # Split into paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        # If adding this paragraph keeps us under limit, accumulate
        if len(current) + len(para) + 2 <= CHUNK_SIZE:
            current = f"{current}\n\n{para}" if current else para
        else:
            # Save current chunk if non-empty
            if current:
                chunks.append(current)
            # If paragraph itself is longer than CHUNK_SIZE, split by character window
            if len(para) > CHUNK_SIZE:
                start = 0
                while start < len(para):
                    end = start + CHUNK_SIZE
                    chunks.append(para[start:end])
                    start = end - CHUNK_OVERLAP
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


# --- OpenAI Embeddings -------------------------------------------------------

EMBEDDING_MODEL = "text-embedding-3-small"


def _has_api_key() -> bool:
    """Check if a real OpenAI API key is configured."""
    from intellibox.config import settings
    return bool(
        settings.openai_api_key
        and not settings.openai_api_key.startswith("sk-placeholder")
    )


def compute_embedding(text: str) -> Optional[List[float]]:
    """Compute an embedding vector for a text string via OpenAI API.

    Returns None if API key is not configured or call fails.
    """
    if not _has_api_key():
        return None

    try:
        from openai import OpenAI

        from intellibox.config import settings

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text[:8000],  # model limit safety
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to compute embedding: {e}")
        return None


def embed_document(doc_id: int) -> int:
    """Chunk a document and compute embeddings for each chunk.

    Args:
        doc_id: ID of the KnowledgeDocument to embed.

    Returns:
        Number of chunks embedded (0 if failed or no API key).
    """
    if not _has_api_key():
        logger.info("Skipping embedding — no OpenAI API key configured")
        return 0

    with get_session() as session:
        doc = session.query(KnowledgeDocument).filter_by(id=doc_id).first()
        if not doc or not doc.extracted_text:
            return 0

        # Remove old chunks for this document
        session.query(KnowledgeChunk).filter_by(document_id=doc_id).delete()

        chunks = chunk_text(doc.extracted_text)
        if not chunks:
            return 0

        try:
            from openai import OpenAI

            from intellibox.config import settings

            client = OpenAI(api_key=settings.openai_api_key)

            # Batch embed all chunks in one API call (more efficient)
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=[c[:8000] for c in chunks],
            )

            for i, embedding_data in enumerate(response.data):
                chunk = KnowledgeChunk(
                    document_id=doc_id,
                    chunk_index=i,
                    chunk_text=chunks[i],
                    embedding=json.dumps(embedding_data.embedding),
                )
                session.add(chunk)

            session.commit()
            logger.info(f"Embedded {len(chunks)} chunks for document {doc_id}")
            return len(chunks)

        except Exception as e:
            logger.error(f"Failed to embed document {doc_id}: {e}")
            session.rollback()
            return 0


def remove_document_chunks(doc_id: int) -> None:
    """Remove all chunks for a document (called on document delete)."""
    with get_session() as session:
        session.query(KnowledgeChunk).filter_by(document_id=doc_id).delete()
        session.commit()


# --- Cosine Similarity -------------------------------------------------------

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalize_score(raw: float, method: str) -> float:
    """Normalize a raw similarity score into a 0-1 display range.

    TF-IDF scores rarely exceed 0.4; embeddings sit in 0.3-0.9.
    This maps both into an intuitive 0-1 range for display as percentages.
    """
    if method == "tfidf":
        # 0.05 → ~15%, 0.15 → ~45%, 0.25 → ~70%, 0.35+ → ~90%+
        return min(1.0, raw * 2.8)
    else:
        # Embeddings: 0.3 → ~25%, 0.5 → ~55%, 0.7 → ~80%, 0.85+ → ~95%+
        return min(1.0, max(0.0, (raw - 0.15) * 1.18))


def _extract_highlight(text: str, max_len: int = 40) -> str:
    """Extract a short distinctive phrase from chunk text for URL highlighting."""
    # Take the first line that has meaningful content
    for line in text.strip().split("\n"):
        line = line.strip().strip("-").strip("*").strip()
        if len(line) >= 10:
            # Trim to word boundary
            if len(line) > max_len:
                cut = line[:max_len].rfind(" ")
                if cut > 15:
                    line = line[:cut]
                else:
                    line = line[:max_len]
            return line
    return text.strip()[:max_len]


# --- Embedding Search --------------------------------------------------------

def _has_embeddings() -> bool:
    """Check if any embedding vectors exist in the database."""
    with get_session() as session:
        count = session.query(KnowledgeChunk).filter(
            KnowledgeChunk.embedding.isnot(None)
        ).count()
        return count > 0


def search_by_embeddings(
    query_text: str,
    top_k: int = 5,
    threshold: float = 0.25,
) -> List[Dict]:
    """Search KB using OpenAI embeddings and cosine similarity.

    Args:
        query_text: The combined action text to search for.
        top_k: Maximum number of results.
        threshold: Minimum similarity score (0-1).

    Returns:
        List of dicts with: doc_id, doc_filename, snippet, score, method
    """
    query_embedding = compute_embedding(query_text)
    if query_embedding is None:
        return []

    results: List[Tuple[float, Dict]] = []

    with get_session() as session:
        chunks = (
            session.query(KnowledgeChunk)
            .filter(KnowledgeChunk.embedding.isnot(None))
            .all()
        )

        for chunk in chunks:
            try:
                chunk_emb = json.loads(chunk.embedding)
            except (json.JSONDecodeError, TypeError):
                continue

            score = _cosine_similarity(query_embedding, chunk_emb)
            if score >= threshold:
                chunk_str = chunk.chunk_text.strip()
                results.append((score, {
                    "doc_id": chunk.document_id,
                    "doc_filename": chunk.document.filename,
                    "snippet": chunk_str[:250],
                    "highlight": _extract_highlight(chunk_str),
                    "score": round(_normalize_score(score, "embeddings"), 2),
                    "raw_score": round(score, 3),
                    "method": "embeddings",
                }))

    # Sort by score descending, take top_k
    results.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate: keep best chunk per document
    seen_docs: set = set()
    unique: List[Dict] = []
    for _score, match in results:
        if match["doc_id"] not in seen_docs:
            seen_docs.add(match["doc_id"])
            unique.append(match)
        if len(unique) >= top_k:
            break

    return unique


# --- TF-IDF Cache & Fallback Search ------------------------------------------

_tfidf_cache: Dict = {
    "corpus_hash": None,
    "vectorizer": None,
    "corpus_vecs": None,
    "corpus_meta": None,
}


def invalidate_tfidf_cache() -> None:
    """Clear the TF-IDF cache (used by tests and after document changes)."""
    _tfidf_cache["corpus_hash"] = None
    _tfidf_cache["vectorizer"] = None
    _tfidf_cache["corpus_vecs"] = None
    _tfidf_cache["corpus_meta"] = None


def _compute_corpus_hash(docs) -> str:
    """Hash document IDs and text lengths to detect changes."""
    import hashlib
    parts = []
    for doc in docs:
        parts.append(f"{doc.id}:{doc.text_length}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def search_by_tfidf(
    query_text: str,
    top_k: int = 5,
    threshold: float = 0.05,
) -> List[Dict]:
    """Search KB using TF-IDF cosine similarity (no API key needed).

    Caches the TF-IDF vectorizer and corpus vectors between calls.
    The cache is invalidated when the document set changes (detected
    via a hash of document IDs and text lengths).

    Args:
        query_text: The combined action text to search for.
        top_k: Maximum number of results.
        threshold: Minimum similarity score (0-1).

    Returns:
        List of dicts with: doc_id, doc_filename, snippet, score, method
    """
    with get_session() as session:
        docs = (
            session.query(KnowledgeDocument)
            .filter(KnowledgeDocument.extraction_status == "success")
            .filter(KnowledgeDocument.extracted_text.isnot(None))
            .all()
        )

        if not docs:
            return []

        # Check if we can reuse the cached vectorizer
        current_hash = _compute_corpus_hash(docs)
        need_rebuild = (
            _tfidf_cache["corpus_hash"] != current_hash
            or _tfidf_cache["vectorizer"] is None
        )

        if need_rebuild:
            # Build corpus: list of (chunk_text, doc_id, doc_filename) tuples
            corpus_meta: List[Tuple[str, int, str]] = []
            corpus_texts: List[str] = []

            for doc in docs:
                chunks = chunk_text(doc.extracted_text)
                for chunk_str in chunks:
                    corpus_texts.append(chunk_str)
                    corpus_meta.append((chunk_str, doc.id, doc.filename))

            if not corpus_texts:
                return []

            vectorizer = TfidfVectorizer(
                stop_words="english",
                max_features=5000,
                ngram_range=(1, 2),
            )

            try:
                corpus_vecs = vectorizer.fit_transform(corpus_texts)
            except ValueError:
                return []

            # Cache everything
            _tfidf_cache["corpus_hash"] = current_hash
            _tfidf_cache["vectorizer"] = vectorizer
            _tfidf_cache["corpus_vecs"] = corpus_vecs
            _tfidf_cache["corpus_meta"] = corpus_meta
        else:
            # Reuse cached data
            vectorizer = _tfidf_cache["vectorizer"]
            corpus_vecs = _tfidf_cache["corpus_vecs"]
            corpus_meta = _tfidf_cache["corpus_meta"]

        # Transform query using the fitted vectorizer (no refit)
        try:
            query_vec = vectorizer.transform([query_text])
        except ValueError:
            return []

        # Compute similarities
        similarities = sklearn_cosine(query_vec, corpus_vecs).flatten()

        # Collect results above threshold
        scored: List[Tuple[float, Dict]] = []
        for i, score in enumerate(similarities):
            if score >= threshold:
                chunk_text_str, doc_id, doc_filename = corpus_meta[i]
                chunk_stripped = chunk_text_str.strip()
                scored.append((float(score), {
                    "doc_id": doc_id,
                    "doc_filename": doc_filename,
                    "snippet": chunk_stripped[:250],
                    "highlight": _extract_highlight(chunk_stripped),
                    "score": round(_normalize_score(float(score), "tfidf"), 2),
                    "raw_score": round(float(score), 3),
                    "method": "tfidf",
                }))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate: keep best chunk per document
        seen_docs: set = set()
        unique: List[Dict] = []
        for _score, match in scored:
            if match["doc_id"] not in seen_docs:
                seen_docs.add(match["doc_id"])
                unique.append(match)
            if len(unique) >= top_k:
                break

        return unique
