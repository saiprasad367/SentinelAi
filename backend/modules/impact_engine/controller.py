"""SentinelAI — Impact Engine Controller"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.impact_engine.service import ImpactService

router = APIRouter(prefix="/impact", tags=["Business Impact"])


@router.post("/{incident_id}")
async def calculate_impact(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """Calculate business impact for an incident."""
    svc = ImpactService(db)
    try:
        assessment = await svc.calculate_impact(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "id": str(assessment.id),
        "incident_id": str(incident_id),
        "impact_level": assessment.impact_level,
        "urgency_score": assessment.urgency_score,
        "severity_score": assessment.severity_score,
        "business_criticality_score": assessment.business_criticality_score,
        "affected_users": assessment.affected_users,
        "affected_percentage": assessment.affected_percentage,
        "revenue_loss_per_minute": assessment.revenue_loss_per_minute,
        "estimated_total_loss": assessment.estimated_total_loss,
        "duration_minutes": assessment.duration_minutes,
        "direct_services": assessment.direct_services,
        "indirect_services": assessment.indirect_services,
        "blast_radius_count": assessment.blast_radius_count,
    }


@router.get("/{incident_id}")
async def get_impact(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get impact assessment for an incident."""
    svc = ImpactService(db)
    assessment = await svc.get_impact(incident_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="No impact assessment found. POST to calculate.")
    return {
        "id": str(assessment.id),
        "impact_level": assessment.impact_level,
        "urgency_score": assessment.urgency_score,
        "business_criticality_score": assessment.business_criticality_score,
        "affected_users": assessment.affected_users,
        "revenue_loss_per_minute": assessment.revenue_loss_per_minute,
        "estimated_total_loss": assessment.estimated_total_loss,
        "blast_radius_count": assessment.blast_radius_count,
        "direct_services": assessment.direct_services,
        "indirect_services": assessment.indirect_services,
    }


@router.get("/{incident_id}/recommendations")
async def get_recommendations(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get AI-generated remediation recommendations."""
    svc = ImpactService(db)
    recs = await svc.get_recommendations(incident_id)
    return [
        {
            "priority": r.priority,
            "title": r.title,
            "description": r.description,
            "action_steps": r.action_steps,
            "expected_recovery_minutes": r.expected_recovery_minutes,
            "confidence": r.confidence,
            "source": r.source,
        }
        for r in recs
    ]
