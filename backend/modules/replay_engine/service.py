"""
SentinelAI — Replay Engine
Incident timeline replay for frontend slider.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared_models import OutageReplay

logger = logging.getLogger("sentinel.replay.service")

REPLAY_EVENT_TYPES = [
    ("healthy",            "System Healthy",        "All services operating normally within SLA"),
    ("latency_spike",      "Latency Spike Detected","P95 latency exceeded 500ms threshold"),
    ("resource_spike",     "Resource Exhaustion",   "CPU/Memory approaching critical thresholds"),
    ("error_rate_rising",  "Error Rate Rising",     "5xx errors increasing beyond warning threshold"),
    ("failure",            "Service Failure",       "Service unavailable, health checks failing"),
    ("cascade",            "Cascade Failure",       "Downstream services impacted by blast radius"),
    ("detection",          "Incident Detected",     "SentinelAI triggered alert and began investigation"),
    ("investigation",      "AI Investigation",      "Root cause analysis running across 12 services"),
    ("mitigation",         "Mitigation Applied",    "Remediation steps executed by on-call engineer"),
    ("recovery",           "Service Recovery",      "Health checks passing, error rate normalizing"),
    ("resolved",           "Fully Resolved",        "All SLAs restored, post-mortem scheduled"),
]


class ReplayService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def seed_replay_events(self, incident_id: UUID) -> List[OutageReplay]:
        """Create synthetic timeline events for an incident (for demo/replay)."""
        from modules.incident_engine.repository import IncidentRepository
        inc_repo = IncidentRepository(self.db)
        incident = await inc_repo.get_by_id(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Check if already seeded
        result = await self.db.execute(
            select(OutageReplay).where(OutageReplay.incident_id == incident_id).limit(1)
        )
        if result.scalar_one_or_none():
            return await self.get_events(incident_id)

        events = []
        base_time = incident.detected_at - timedelta(minutes=30)
        for i, (evt_type, evt_name, evt_detail) in enumerate(REPLAY_EVENT_TYPES):
            event = OutageReplay(
                incident_id=incident_id,
                event_type=evt_type,
                event_name=evt_name,
                event_detail=evt_detail,
                affected_service=incident.affected_service or "payment-api",
                sequence_order=i,
                event_timestamp=base_time + timedelta(minutes=i * 3),
                metric_snapshot={
                    "cpu": min(95, 20 + i * 8),
                    "memory": min(92, 30 + i * 6),
                    "error_rate": min(45, i * 4) if i > 2 else 0,
                    "latency_ms": min(2000, 80 + i * 180) if i > 0 else 80,
                },
            )
            self.db.add(event)
            events.append(event)

        await self.db.flush()
        logger.info(f"Seeded {len(events)} replay events for incident {incident_id}")
        return events

    async def get_events(self, incident_id: UUID) -> List[OutageReplay]:
        result = await self.db.execute(
            select(OutageReplay)
            .where(OutageReplay.incident_id == incident_id)
            .order_by(OutageReplay.sequence_order)
        )
        return result.scalars().all()
