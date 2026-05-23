"""SentinelAI — Replay Engine Controller"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.replay_engine.service import ReplayService

router = APIRouter(prefix="/replay", tags=["Incident Replay"])


@router.get("/{incident_id}/events")
async def get_replay_events(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all replay events for an incident timeline."""
    svc = ReplayService(db)
    events = await svc.get_events(incident_id)
    if not events:
        # Auto-seed if empty
        try:
            events = await svc.seed_replay_events(incident_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return [
        {
            "sequence": e.sequence_order,
            "type": e.event_type,
            "name": e.event_name,
            "detail": e.event_detail,
            "affected_service": e.affected_service,
            "timestamp": e.event_timestamp.isoformat(),
            "metrics": e.metric_snapshot,
        }
        for e in events
    ]


@router.post("/{incident_id}/seed")
async def seed_replay_events(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """Seed replay timeline events for demo/testing."""
    svc = ReplayService(db)
    try:
        events = await svc.seed_replay_events(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"events_created": len(events), "incident_id": str(incident_id)}
