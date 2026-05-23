"""
SentinelAI — Impact Engine
Business impact scoring + blast radius integration.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.events import EventType, event_bus
from modules.shared_models import ImpactAssessment, Recommendation

logger = logging.getLogger("sentinel.impact.service")

# Severity to user impact mapping
SEVERITY_USER_IMPACT = {
    "P1": 1.0,    # 100% users affected
    "P2": 0.5,    # 50%
    "P3": 0.15,   # 15%
    "P4": 0.02,   # 2%
}

SEVERITY_URGENCY = {"P1": 95, "P2": 75, "P3": 50, "P4": 20}


class ImpactService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_impact(self, incident_id: UUID) -> ImpactAssessment:
        """
        Calculate full business impact for an incident.
        Uses severity, affected services, and blast radius.
        """
        from modules.incident_engine.repository import IncidentRepository
        inc_repo = IncidentRepository(self.db)
        incident = await inc_repo.get_by_id(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # ── Compute blast radius ───────────────────────────────────────────────
        direct_services = incident.affected_services or []
        indirect_services = []
        if incident.affected_service:
            try:
                from modules.graph_engine.service import GraphService
                graph_svc = GraphService(self.db)
                blast = await graph_svc.compute_blast_radius(incident.affected_service)
                direct_services = blast.get("direct_impact", direct_services)
                indirect_services = blast.get("indirect_impact", [])
            except Exception as e:
                logger.warning(f"Blast radius failed: {e}")

        total_impacted = len(set(direct_services + indirect_services))

        # ── Scoring ────────────────────────────────────────────────────────────
        severity = incident.severity or "P3"
        affected_pct = SEVERITY_USER_IMPACT.get(severity, 0.15)
        affected_users = int(settings.critical_user_threshold * affected_pct)

        urgency_score = SEVERITY_URGENCY.get(severity, 50)
        severity_score = min(100.0, urgency_score + total_impacted * 3)
        business_criticality = min(100.0, severity_score * 0.7 + affected_pct * 30)

        # ── Revenue Loss ───────────────────────────────────────────────────────
        revenue_per_min = settings.revenue_per_minute_usd
        # P1 gets full revenue impact, scaled by severity
        revenue_multiplier = {"P1": 1.0, "P2": 0.5, "P3": 0.15, "P4": 0.02}.get(severity, 0.15)
        revenue_per_min_loss = revenue_per_min * revenue_multiplier

        # Estimate duration from incident age
        duration_minutes = max(
            5.0,
            (datetime.now(timezone.utc) - incident.detected_at).total_seconds() / 60,
        )
        total_revenue_loss = revenue_per_min_loss * duration_minutes

        # ── Determine impact level ─────────────────────────────────────────────
        if business_criticality >= 80:
            impact_level = "critical"
        elif business_criticality >= 60:
            impact_level = "high"
        elif business_criticality >= 35:
            impact_level = "medium"
        else:
            impact_level = "low"

        # ── Store assessment ───────────────────────────────────────────────────
        assessment = ImpactAssessment(
            incident_id=incident_id,
            impact_level=impact_level,
            urgency_score=urgency_score,
            severity_score=severity_score,
            business_criticality_score=business_criticality,
            affected_users=affected_users,
            affected_percentage=affected_pct * 100,
            revenue_loss_per_minute=revenue_per_min_loss,
            estimated_total_loss=total_revenue_loss,
            duration_minutes=duration_minutes,
            direct_services=direct_services,
            indirect_services=indirect_services,
            blast_radius_count=total_impacted,
        )
        self.db.add(assessment)
        await self.db.flush()

        await event_bus.emit(
            EventType.IMPACT_CALCULATED,
            payload={
                "incident_id": str(incident_id),
                "impact_level": impact_level,
                "affected_users": affected_users,
                "revenue_loss": total_revenue_loss,
                "blast_radius": total_impacted,
            },
            incident_id=str(incident_id),
        )

        # ── Generate AI recommendations ────────────────────────────────────────
        await self._generate_recommendations(incident_id, incident, assessment)

        return assessment

    async def _generate_recommendations(
        self,
        incident_id: UUID,
        incident: Any,
        assessment: ImpactAssessment,
    ) -> None:
        """Generate AI-powered remediation recommendations."""
        from shared.ai.openrouter import get_openrouter
        ai = get_openrouter()

        prompt = f"""Generate 3 specific remediation recommendations for this incident:

INCIDENT: {incident.title}
SEVERITY: {incident.severity}
AFFECTED SERVICE: {incident.affected_service or 'Unknown'}
BLAST RADIUS: {assessment.blast_radius_count} services
ROOT CAUSE: {incident.root_cause or 'Under investigation'}
IMPACT: {assessment.impact_level} - {assessment.affected_users:,} users affected

For each recommendation provide:
- TITLE: (short action title)
- STEPS: (numbered action steps, max 3)
- ETA: (estimated recovery time in minutes)
- CONFIDENCE: (0-100)

Format as JSON array with fields: title, steps (array), eta_minutes, confidence"""

        try:
            response = await ai.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.3,
            )

            import json, re
            # Extract JSON from response
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                recs = json.loads(json_match.group())
                for i, rec in enumerate(recs[:3]):
                    recommendation = Recommendation(
                        incident_id=incident_id,
                        priority=i + 1,
                        title=rec.get("title", f"Recommendation {i+1}"),
                        description="\n".join(rec.get("steps", [])),
                        action_steps=rec.get("steps", []),
                        expected_recovery_minutes=rec.get("eta_minutes"),
                        confidence=rec.get("confidence", 70) / 100.0,
                        source="ai",
                    )
                    self.db.add(recommendation)
                await self.db.flush()

                await event_bus.emit(
                    EventType.RECOMMENDATION_GENERATED,
                    payload={"incident_id": str(incident_id), "count": len(recs)},
                )
        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")

    async def get_impact(self, incident_id: UUID) -> Optional[ImpactAssessment]:
        from sqlalchemy import select, desc
        result = await self.db.execute(
            select(ImpactAssessment)
            .where(ImpactAssessment.incident_id == incident_id)
            .order_by(desc(ImpactAssessment.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_recommendations(self, incident_id: UUID) -> List[Recommendation]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Recommendation)
            .where(Recommendation.incident_id == incident_id)
            .order_by(Recommendation.priority)
        )
        return result.scalars().all()
