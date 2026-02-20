"""Test-only endpoints gated by TESTING env var."""

from datetime import datetime

from fastapi import APIRouter, Request

from intellibox.models import (
    Action,
    Assignment,
    Email,
    KnowledgeChunk,
    KnowledgeDocument,
    RosterMember,
)
from intellibox.web.deps import get_session

router = APIRouter()


@router.post("/api/test/reset")
async def test_reset_database():
    """Drop and recreate all tables. Only available when TESTING=true."""
    from intellibox.database import engine
    from intellibox.models import Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return {"status": "reset", "tables": list(Base.metadata.tables.keys())}


@router.post("/api/test/seed")
async def test_seed_entity(request: Request):
    """Create a test entity. Body: {"type": "email|action|assignment|roster_member", "data": {...}}"""
    payload = await request.json()
    entity_type = payload["type"]
    data = payload["data"]

    # Parse ISO date strings into datetime objects
    _date_fields = {
        "received_date", "processed_at", "due_date", "assigned_at", "completed_at", "created_at"
    }
    for key in list(data.keys()):
        if key in _date_fields and isinstance(data[key], str):
            data[key] = datetime.fromisoformat(data[key])

    model_map = {
        "email": Email,
        "action": Action,
        "assignment": Assignment,
        "roster_member": RosterMember,
        "knowledge_document": KnowledgeDocument,
        "knowledge_chunk": KnowledgeChunk,
    }
    Model = model_map[entity_type]

    with get_session() as session:
        entity = Model(**data)
        session.add(entity)
        session.flush()
        entity_id = entity.id
    return {"id": entity_id}


@router.get("/api/test/query/action/{action_id}")
async def test_query_action(action_id: int):
    """Query an action by ID for test assertions."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()
        if not action:
            return {"found": False}
        return {
            "found": True,
            "id": action.id,
            "title": action.title,
            "priority": action.priority,
            "due_date": action.due_date.isoformat() if action.due_date else None,
            "category": action.category,
            "has_assignments": bool(action.assignments and len(action.assignments) > 0),
        }


@router.get("/api/test/query/assignment")
async def test_query_assignment(action_id: int):
    """Query an active assignment by action_id for test assertions."""
    with get_session() as session:
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()
        if not assignment:
            return {"found": False}
        return {
            "found": True,
            "id": assignment.id,
            "action_id": assignment.action_id,
            "assigned_to": assignment.assigned_to,
            "status": assignment.status,
        }


@router.get("/api/test/query/roster/count")
async def test_query_roster_count():
    """Count roster members for test assertions."""
    with get_session() as session:
        count = session.query(RosterMember).count()
        return {"count": count}


@router.get("/api/test/query/roster-member/{member_id}")
async def test_query_roster_member(member_id: int):
    """Query a roster member by ID for test assertions."""
    with get_session() as session:
        member = session.query(RosterMember).filter_by(id=member_id).first()
        if not member:
            return {"found": False}
        return {"found": True, "id": member.id}


@router.get("/api/test/query/knowledge/count")
async def test_query_knowledge_count():
    """Count knowledge documents for test assertions."""
    with get_session() as session:
        count = session.query(KnowledgeDocument).count()
        return {"count": count}
