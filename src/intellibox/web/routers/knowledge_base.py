"""Knowledge base routes."""

from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from intellibox.models import KnowledgeDocument
from intellibox.web.deps import get_session, templates

router = APIRouter()

ALLOWED_KB_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}
MAX_KB_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.get("/knowledge-base", response_class=HTMLResponse)
async def knowledge_base(request: Request):
    """Redirect legacy KB page to the Settings Knowledge Base tab."""
    return RedirectResponse("/settings?tab=kb", status_code=302)


@router.post("/knowledge-base/upload")
async def upload_knowledge_doc(
    file: UploadFile = File(...),
    description: str = Form(""),
):
    """Upload a document to the knowledge base."""
    from intellibox.knowledge.extractor import extract_text

    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_KB_EXTENSIONS:
        return RedirectResponse(
            "/settings?tab=kb&kb_error=Unsupported+file+type.+Please+upload+PDF,+DOCX,+or+TXT",
            status_code=303,
        )

    file_type = ALLOWED_KB_EXTENSIONS[ext]
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_KB_FILE_SIZE:
        return RedirectResponse(
            "/settings?tab=kb&kb_error=File+too+large.+Maximum+size+is+10+MB",
            status_code=303,
        )

    if file_size == 0:
        return RedirectResponse(
            "/settings?tab=kb&kb_error=File+is+empty",
            status_code=303,
        )

    extracted_text, status = extract_text(content, file_type)

    with get_session() as session:
        doc = KnowledgeDocument(
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            description=description.strip() if description.strip() else None,
            extracted_text=extracted_text if extracted_text else None,
            extraction_status=status,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    if status == "failed":
        return RedirectResponse(
            "/settings?tab=kb&kb_warning=File+uploaded+but+text+extraction+failed",
            status_code=303,
        )
    elif status == "partial":
        return RedirectResponse(
            "/settings?tab=kb&kb_warning=File+uploaded+but+only+partial+text+could+be+extracted",
            status_code=303,
        )

    # Compute embeddings if API key is available (non-blocking best-effort)
    from intellibox.knowledge.embeddings import embed_document
    chunk_count = embed_document(doc_id)
    if chunk_count > 0:
        return RedirectResponse(
            f"/settings?tab=kb&kb_success=1&embedded={chunk_count}",
            status_code=303,
        )

    return RedirectResponse("/settings?tab=kb&kb_success=1", status_code=303)


@router.get("/knowledge-base/{doc_id}", response_class=HTMLResponse)
async def knowledge_base_detail(request: Request, doc_id: int, highlight: Optional[str] = None):
    """View a knowledge base document and its extracted text."""
    with get_session() as session:
        doc = session.query(KnowledgeDocument).filter_by(id=doc_id).first()
        if not doc:
            return RedirectResponse("/settings?tab=kb", status_code=303)
        return templates.TemplateResponse("knowledge_base_detail.html", {
            "request": request,
            "doc": doc,
            "highlight": highlight or "",
        })


@router.post("/knowledge-base/{doc_id}/delete")
async def delete_knowledge_doc(doc_id: int):
    """Delete a document and its embedding chunks from the knowledge base."""
    from intellibox.knowledge.embeddings import remove_document_chunks
    remove_document_chunks(doc_id)
    with get_session() as session:
        doc = session.query(KnowledgeDocument).filter_by(id=doc_id).first()
        if doc:
            session.delete(doc)
            session.commit()
    return RedirectResponse("/settings?tab=kb&kb_deleted=1", status_code=303)
