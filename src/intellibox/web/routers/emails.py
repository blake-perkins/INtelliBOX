"""Email list, detail, and upload routes."""

import json as _json
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc, or_

from intellibox.audit import log_audit
from intellibox.models import Action, Email, KnowledgeDocument
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.auth import require_admin
from intellibox.web.deps import get_session, templates
from intellibox.web.queries import get_banner_stats, get_time_since_last_email, paginate

router = APIRouter()

ALLOWED_CONTEXT_EXTENSIONS = {
    ".pdf": "pdf", ".docx": "docx", ".txt": "txt",
    ".md": "md", ".csv": "csv", ".json": "json",
    ".html": "html", ".xml": "xml", ".rtf": "rtf", ".log": "log",
}
MAX_CONTEXT_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EMAIL_EXTENSIONS = {".eml", ".msg"}
MAX_EMAIL_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


@router.get("/emails", response_class=HTMLResponse)
async def list_emails(
    request: Request,
    search: Optional[str] = None,
    processed: Optional[str] = None,
    days: Optional[str] = None,
    page: int = Query(1, ge=1)
):
    """List all emails."""
    days_int = int(days) if days and days.strip().isdigit() else None
    with get_session() as session:
        stats = get_banner_stats(session)
        time_since_last_email = get_time_since_last_email(session)

        # Get stats
        total_emails = session.query(Email).count()
        processed_emails = session.query(Email).filter(Email.processed == True).count()
        unprocessed_emails = total_emails - processed_emails

        # Count emails with high priority actions
        emails_with_high_priority = session.query(Email).join(Action).filter(
            Action.priority == "high"
        ).distinct().count()

        # Base query
        query = session.query(Email)

        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Email.subject.ilike(search_term),
                    Email.from_address.ilike(search_term),
                    Email.body_text.ilike(search_term)
                )
            )

        if processed == "true":
            query = query.filter(Email.processed == True)
        elif processed == "false":
            query = query.filter(Email.processed == False)

        # Date range filter
        if days_int:
            cutoff_date = utcnow() - timedelta(days=days_int)
            query = query.filter(Email.received_date >= cutoff_date)

        # Order by received date
        query = query.order_by(desc(Email.received_date))

        # Pagination
        emails, total_count, total_pages = paginate(query, page)

        return templates.TemplateResponse("emails.html", {
            "request": request,
            "emails": emails,
            "search": search,
            "processed": processed,
            "days": days,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "total_emails": total_emails,
            "processed_emails": processed_emails,
            "unprocessed_emails": unprocessed_emails,
            "emails_with_high_priority": emails_with_high_priority,
            "unassigned_actions": stats["unassigned_actions"],
            "high_priority": stats["high_priority"],
            "overdue_count": stats["overdue_count"],
            "time_since_last_email": time_since_last_email,
            "current_time": utcnow()
        })


@router.post("/emails/upload")
async def upload_email(file: UploadFile = File(...)):
    """Upload an .eml or .msg file for processing."""
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EMAIL_EXTENSIONS:
        return RedirectResponse(
            "/emails?upload_error=Unsupported+file+type.+Please+upload+.eml+or+.msg",
            status_code=303,
        )

    content = await file.read()
    if len(content) > MAX_EMAIL_FILE_SIZE:
        return RedirectResponse(
            "/emails?upload_error=File+too+large.+Maximum+size+is+25+MB",
            status_code=303,
        )
    if len(content) == 0:
        return RedirectResponse(
            "/emails?upload_error=File+is+empty",
            status_code=303,
        )

    inbox_dir = Path("data/inbox")
    inbox_dir.mkdir(parents=True, exist_ok=True)
    dest = inbox_dir / filename

    # Avoid overwriting existing files
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = inbox_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    dest.write_bytes(content)
    return RedirectResponse("/emails?uploaded=1", status_code=303)


@router.get("/emails/{email_id}", response_class=HTMLResponse)
async def view_email(request: Request, email_id: int):
    """View details of a specific email."""
    with get_session() as session:
        email = session.query(Email).filter_by(id=email_id).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get associated actions
        actions = session.query(Action).filter_by(email_id=email_id).all()

        # Count actions by status
        assigned_count = sum(1 for action in actions if action.assignments)
        unassigned_count = len(actions) - assigned_count
        completed_count = sum(1 for action in actions if action.assignments and action.assignments[0].status == 'completed')

        # Count by priority
        high_priority_count = sum(1 for action in actions if action.priority == 'high')

        # Parse also_received_from JSON for template
        also_received = _json.loads(email.also_received_from) if email.also_received_from else []

        return templates.TemplateResponse("email_detail.html", {
            "request": request,
            "email": email,
            "actions": actions,
            "assigned_count": assigned_count,
            "unassigned_count": unassigned_count,
            "completed_count": completed_count,
            "high_priority_count": high_priority_count,
            "also_received": also_received,
            "current_time": utcnow()
        })


# ── Reprocess routes (admin-only) ─────────────────────────────────────────


@router.get("/emails/{email_id}/reprocess", response_class=HTMLResponse,
            dependencies=[Depends(require_admin)])
async def reprocess_form(request: Request, email_id: int):
    """Show the reprocess form for an email."""
    with get_session() as session:
        email = session.query(Email).filter_by(id=email_id).first()
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        actions = session.query(Action).filter_by(email_id=email_id).all()
        assigned_actions = [a for a in actions if a.assignments]
        unassigned_actions = [a for a in actions if not a.assignments]

        kb_docs = session.query(KnowledgeDocument).order_by(
            KnowledgeDocument.uploaded_at.desc()
        ).all()

        return templates.TemplateResponse("reprocess_form.html", {
            "request": request,
            "email": email,
            "assigned_count": len(assigned_actions),
            "unassigned_count": len(unassigned_actions),
            "total_actions": len(actions),
            "kb_docs": kb_docs,
        })


@router.post("/emails/{email_id}/reprocess", response_class=HTMLResponse,
             dependencies=[Depends(require_admin)])
async def reprocess_preview(
    request: Request,
    email_id: int,
    context_notes: str = Form(""),
    context_files: List[UploadFile] = File([]),
    add_to_kb: Optional[str] = Form(None),
    kb_doc_ids: List[int] = Form([]),
):
    """Run AI on the email and show a preview of new vs existing actions."""
    with get_session() as session:
        email = session.query(Email).filter_by(id=email_id).first()
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # ── Build additional context from files + notes ──
        additional_context = ""
        kb_data_list = []  # metadata for optional KB save

        for cf in context_files:
            if not cf.filename:
                continue
            filename = cf.filename
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ALLOWED_CONTEXT_EXTENSIONS:
                return RedirectResponse(
                    f"/emails/{email_id}/reprocess?error=Unsupported+file+type:+{filename}.+Use+a+supported+format",
                    status_code=303,
                )
            file_content = await cf.read()
            if len(file_content) > MAX_CONTEXT_FILE_SIZE:
                return RedirectResponse(
                    f"/emails/{email_id}/reprocess?error=File+too+large:+{filename}.+Maximum+is+10+MB",
                    status_code=303,
                )
            if len(file_content) == 0:
                continue
            from intellibox.knowledge.extractor import extract_text
            file_type = ALLOWED_CONTEXT_EXTENSIONS[ext]
            extracted_text, extraction_status = extract_text(file_content, file_type)
            if extracted_text:
                if additional_context:
                    additional_context += "\n\n"
                additional_context += f"--- {filename} ---\n{extracted_text}"
            # Save KB metadata if user checked "add to KB"
            if add_to_kb and extracted_text:
                kb_data_list.append({
                    "filename": filename,
                    "file_type": file_type,
                    "file_size": len(file_content),
                    "extracted_text": extracted_text,
                    "extraction_status": extraction_status,
                })

        if context_notes.strip():
            if additional_context:
                additional_context += "\n\n"
            additional_context += context_notes.strip()

        # ── Include selected Knowledge Base documents ──
        if kb_doc_ids:
            selected_kb_docs = session.query(KnowledgeDocument).filter(
                KnowledgeDocument.id.in_(kb_doc_ids)
            ).all()
            for doc in selected_kb_docs:
                if doc.extracted_text:
                    if additional_context:
                        additional_context += "\n\n"
                    additional_context += f"--- {doc.filename} (Knowledge Base) ---\n{doc.extracted_text}"

        # ── Run AI extraction (no DB changes) ──
        from intellibox.ai.processor import get_ai_client
        client = get_ai_client()
        action_dicts, raw_response = client.extract_actions(
            email,
            additional_context=additional_context if additional_context else None,
        )
        # Build preview Action objects (NOT saved)
        new_actions = client.create_action_objects(email, action_dicts, raw_response)

        # ── Split current actions into preserved vs replaceable ──
        current_actions = session.query(Action).filter_by(email_id=email_id).all()
        preserved = [a for a in current_actions if a.assignments]
        replaceable = [a for a in current_actions if not a.assignments]

        kb_docs = session.query(KnowledgeDocument).order_by(
            KnowledgeDocument.uploaded_at.desc()
        ).all()

        return templates.TemplateResponse("reprocess_preview.html", {
            "request": request,
            "email": email,
            "kb_docs": kb_docs,
            "preserved_actions": preserved,
            "replaceable_actions": replaceable,
            "new_actions": new_actions,
            "action_dicts_json": _json.dumps(action_dicts),
            "raw_response": raw_response,
            "kb_data_json": _json.dumps(kb_data_list) if kb_data_list else "",
        })


@router.post("/emails/{email_id}/reprocess/confirm",
             dependencies=[Depends(require_admin)])
async def reprocess_confirm(
    request: Request,
    email_id: int,
    action_dicts_json: str = Form(...),
    raw_response: str = Form(...),
    kb_data_json: str = Form(""),
):
    """Commit the reprocess: delete unassigned actions, create new ones."""
    with get_session() as session:
        email = session.query(Email).filter_by(id=email_id).first()
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Count what we're replacing
        current_actions = session.query(Action).filter_by(email_id=email_id).all()
        preserved = [a for a in current_actions if a.assignments]
        replaceable = [a for a in current_actions if not a.assignments]
        replaced_count = len(replaceable)

        # Delete only unassigned actions
        for action in replaceable:
            session.delete(action)

        # Create new actions from the serialized dicts
        action_dicts = _json.loads(action_dicts_json)
        from intellibox.ai.processor import get_ai_client
        client = get_ai_client()
        new_actions = client.create_action_objects(email, action_dicts, raw_response)
        for action in new_actions:
            session.add(action)

        # Mark email as processed
        email.processed = True
        email.processed_at = utcnow()

        # Optional: save context files to Knowledge Base
        added_to_kb = False
        kb_doc_ids = []
        if kb_data_json:
            try:
                kb_data_parsed = _json.loads(kb_data_json)
                if isinstance(kb_data_parsed, dict):
                    kb_data_parsed = [kb_data_parsed]
                for kb_data in kb_data_parsed:
                    doc = KnowledgeDocument(
                        filename=kb_data["filename"],
                        file_type=kb_data["file_type"],
                        file_size=kb_data["file_size"],
                        description=f"Uploaded during reprocess of email #{email_id}",
                        extracted_text=kb_data["extracted_text"],
                        extraction_status=kb_data["extraction_status"],
                    )
                    session.add(doc)
                    session.flush()
                    kb_doc_ids.append(doc.id)
                    added_to_kb = True
            except (ValueError, KeyError):
                pass  # skip KB save on bad data

        # Audit log
        log_audit(session, request, "reprocess", "email", email_id, {
            "preserved_count": len(preserved),
            "replaced_count": replaced_count,
            "new_count": len(new_actions),
            "added_to_kb": added_to_kb,
        })
        session.commit()

        # Trigger KB embeddings after commit (best-effort)
        if kb_doc_ids:
            try:
                from intellibox.knowledge.embeddings import embed_document
                for kb_id in kb_doc_ids:
                    embed_document(kb_id)
            except Exception:
                pass

        if len(new_actions) > 0:
            return RedirectResponse(
                f"/emails/{email_id}?reprocessed={len(new_actions)}",
                status_code=303,
            )
        else:
            return RedirectResponse(
                f"/emails/{email_id}?reprocess_warning=no_actions",
                status_code=303,
            )
