"""
SentinelAI — Investigation Engine Controller
/api/v1/investigations - SSE streaming + CRUD
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.investigation_engine.service import InvestigationService, investigation_sse_stream

logger = logging.getLogger("sentinel.investigation.controller")
router = APIRouter(prefix="/investigations", tags=["Investigations"])


@router.post("/", status_code=201)
async def start_investigation(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI investigation workflow for an incident."""
    svc = InvestigationService(db)
    try:
        inv = await svc.start_investigation(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "investigation_id": str(inv.id),
        "incident_id": str(incident_id),
        "status": inv.status,
        "message": "Investigation started. Connect to /stream for live updates.",
    }


@router.get("/{investigation_id}")
async def get_investigation(investigation_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get investigation details and current step statuses."""
    svc = InvestigationService(db)
    inv = await svc.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    steps = await svc.get_steps(investigation_id)
    return {
        "id": str(inv.id),
        "incident_id": str(inv.incident_id),
        "status": inv.status,
        "root_cause": inv.root_cause,
        "confidence": inv.root_cause_confidence,
        "causal_chain": inv.causal_chain,
        "resolution_suggestions": inv.resolution_suggestions,
        "ai_narrative": inv.ai_narrative,
        "model_used": inv.model_used,
        "started_at": inv.started_at.isoformat() if inv.started_at else None,
        "completed_at": inv.completed_at.isoformat() if inv.completed_at else None,
        "steps": [
            {
                "order": s.step_order,
                "name": s.step_name,
                "description": s.step_description,
                "status": s.status,
                "confidence": s.confidence,
                "ai_reasoning": s.ai_reasoning,
            }
            for s in steps
        ],
    }


@router.get("/{investigation_id}/steps")
async def get_investigation_steps(investigation_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all investigation steps and their current status."""
    svc = InvestigationService(db)
    steps = await svc.get_steps(investigation_id)
    return [
        {
            "order": s.step_order,
            "name": s.step_name,
            "description": s.step_description,
            "status": s.status,
            "confidence": s.confidence,
            "ai_reasoning": s.ai_reasoning,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        for s in steps
    ]


@router.get("/{investigation_id}/stream")
async def stream_investigation(investigation_id: UUID, request: Request):
    """
    SSE endpoint - streams investigation step progress in real time.
    Frontend connects here to see the AI 'thinking' live.
    """
    async def event_generator():
        async for event in investigation_sse_stream(investigation_id):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/incident/{incident_id}")
async def list_investigations_by_incident(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all investigations for a given incident."""
    svc = InvestigationService(db)
    invs = await svc.list_by_incident(incident_id)
    return [
        {
            "id": str(i.id),
            "status": i.status,
            "confidence": i.root_cause_confidence,
            "created_at": i.created_at.isoformat(),
        }
        for i in invs
    ]
