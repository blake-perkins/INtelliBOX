"""Settings and category management routes."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import desc

from intellibox.models import KnowledgeDocument, RosterMember
from intellibox.settings_service import SettingsService
from intellibox.web.auth import require_admin
from intellibox.web.deps import get_session, templates

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, success: bool = False):
    """Settings page for configuring priority rules."""
    priority_config = SettingsService.get_priority_config()
    ai_config = SettingsService.get_ai_config()
    high_senders = priority_config.get('high_senders', [])
    high_keywords = priority_config.get('high_keywords', [])
    categories = ai_config.get('categories', SettingsService.DEFAULT_CATEGORIES)

    with get_session() as session:
        roster = session.query(RosterMember).order_by(
            RosterMember.last_name, RosterMember.first_name
        ).all()

        # Knowledge Base data
        kb_documents = session.query(KnowledgeDocument).order_by(
            desc(KnowledgeDocument.uploaded_at)
        ).all()
        kb_total_size_bytes = sum(d.file_size for d in kb_documents)
        kb_total_chars = sum(d.text_length for d in kb_documents)
        if kb_total_size_bytes < 1024:
            kb_total_size = f"{kb_total_size_bytes} B"
        elif kb_total_size_bytes < 1024 * 1024:
            kb_total_size = f"{kb_total_size_bytes / 1024:.1f} KB"
        else:
            kb_total_size = f"{kb_total_size_bytes / (1024 * 1024):.1f} MB"

        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "priority_default": priority_config.get('default_priority', 'medium'),
                "priority_days_threshold": priority_config.get('days_threshold', 5),
                "priority_high_senders_text": '\n'.join(high_senders),
                "priority_high_keywords_text": '\n'.join(high_keywords),
                "confidence_threshold": ai_config.get('confidence_threshold', 0.5),
                "categories": categories,
                "timezone": SettingsService.get_timezone(),
                "program_name": SettingsService.get_setting('program_name', ''),
                "insights_prompt": SettingsService.get_insights_prompt(),
                "success": success,
                "roster": roster,
                "kb_documents": kb_documents,
                "kb_total_size": kb_total_size,
                "kb_total_chars": kb_total_chars,
            }
        )


@router.post("/settings")
async def save_settings(
    request: Request,
    priority_default: str = Form(...),
    priority_days_threshold: int = Form(...),
    priority_high_senders: str = Form(""),
    priority_high_keywords: str = Form(""),
    confidence_threshold: float = Form(0.5),
    timezone: str = Form("America/Chicago"),
    program_name: str = Form("")
):
    """Save priority and AI settings."""
    # Parse textarea inputs (newline-separated) into lists
    senders = [s.strip() for s in priority_high_senders.split('\n') if s.strip()]
    keywords = [k.strip() for k in priority_high_keywords.split('\n') if k.strip()]

    # Save settings
    SettingsService.set_setting('priority_default', priority_default)
    SettingsService.set_setting('priority_days_threshold', priority_days_threshold)
    SettingsService.set_setting('priority_high_senders', senders)
    SettingsService.set_setting('priority_high_keywords', keywords)
    SettingsService.set_setting('ai_confidence_threshold', round(float(confidence_threshold), 2))
    SettingsService.set_setting('timezone', timezone)
    SettingsService.set_setting('program_name', program_name.strip())

    # Redirect with success flag
    return RedirectResponse(url="/settings?success=true", status_code=303)


@router.post("/settings/insights-prompt")
async def save_insights_prompt(insights_prompt: str = Form(...)):
    """Save custom insights prompt template."""
    SettingsService.set_setting(
        "insights_prompt", insights_prompt,
        description="Custom prompt template for Insights page AI analysis"
    )
    return RedirectResponse(url="/settings?tab=prompt&prompt_saved=1", status_code=303)


@router.post("/settings/insights-prompt/reset")
async def reset_insights_prompt():
    """Reset insights prompt to hardcoded default."""
    SettingsService.delete_setting("insights_prompt")
    return JSONResponse({"status": "ok"})


@router.post("/categories/add")
async def add_category(name: str = Form(...), description: str = Form("")):
    """Add a new action category."""
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings?tab=categories&cat_error=Name+is+required", status_code=303)
    ai_config = SettingsService.get_ai_config()
    categories = ai_config.get('categories', list(SettingsService.DEFAULT_CATEGORIES))
    if any(c['name'].lower() == name.lower() for c in categories):
        return RedirectResponse(url=f"/settings?tab=categories&cat_error=Category+%27{name}%27+already+exists", status_code=303)
    categories.append({"name": name, "description": description.strip()})
    SettingsService.set_setting('ai_categories', categories)
    return RedirectResponse(url=f"/settings?tab=categories&cat_added={name}", status_code=303)


@router.post("/categories/delete")
async def delete_category(name: str = Form(...)):
    """Remove an action category."""
    ai_config = SettingsService.get_ai_config()
    categories = ai_config.get('categories', list(SettingsService.DEFAULT_CATEGORIES))
    categories = [c for c in categories if c['name'] != name]
    SettingsService.set_setting('ai_categories', categories)
    return RedirectResponse(url=f"/settings?tab=categories&cat_deleted={name}", status_code=303)
