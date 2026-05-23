"""SentinelAI — Analytics Engine Controller"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.analytics_engine.service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    """Get current analytics summary: MTTR, MTBF, trends."""
    svc = AnalyticsService(db)
    return await svc.get_summary()


@router.post("/snapshot")
async def create_snapshot(db: AsyncSession = Depends(get_db)):
    """Manually trigger analytics aggregation snapshot."""
    svc = AnalyticsService(db)
    snapshot = await svc.aggregate_snapshot()
    return {
        "snapshot_id": str(snapshot.id),
        "total_incidents": snapshot.total_incidents,
        "avg_mttr_minutes": snapshot.avg_mttr_minutes,
        "snapshot_at": snapshot.snapshot_at.isoformat(),
    }
