"""
SentinelAI — Investigation Engine Service + Controller
Handles investigation creation, SSE streaming, and step retrieval.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_context
from modules.investigation_engine.models import Investigation
from modules.investigation_engine.repository import InvestigationRepository, InvestigationStepRepository

logger = logging.getLogger("sentinel.investigation.service")


class InvestigationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InvestigationRepository(db)
        self.step_repo = InvestigationStepRepository(db)

    async def start_investigation(self, incident_id: UUID) -> Investigation:
        """Create investigation record and launch background workflow."""
        from modules.incident_engine.repository import IncidentRepository, LogRepository
        inc_repo = IncidentRepository(self.db)
        log_repo = LogRepository(self.db)

        incident = await inc_repo.get_by_id(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Create investigation record
        inv = await self.repo.create(
            incident_id=incident_id,
            status="pending",
        )
        await self.db.commit()

        # Fetch log samples for context
        error_logs = await log_repo.get_errors(incident_id)
        logs_sample = [log.message for log in error_logs[:15]]

        # Launch investigation in background (non-blocking)
        asyncio.create_task(
            self._run_investigation_background(
                investigation_id=inv.id,
                incident_id=incident_id,
                incident_title=incident.title,
                incident_description=incident.description,
                affected_service=incident.affected_service,
                logs_sample=logs_sample,
            )
        )

        return inv

    async def _run_investigation_background(
        self,
        investigation_id: UUID,
        incident_id: UUID,
        incident_title: str,
        incident_description: Optional[str],
        affected_service: Optional[str],
        logs_sample: List[str],
    ) -> None:
        """Run in background - uses its own DB session."""
        from modules.investigation_engine.workflow import run_investigation
        async with get_db_context() as db:
            try:
                await run_investigation(
                    investigation_id=investigation_id,
                    incident_id=incident_id,
                    incident_title=incident_title,
                    incident_description=incident_description,
                    affected_service=affected_service,
                    logs_sample=logs_sample,
                    db=db,
                )
            except Exception as e:
                logger.error(f"Investigation {investigation_id} failed: {e}")

    async def get_investigation(self, inv_id: UUID) -> Optional[Investigation]:
        return await self.repo.get_by_id(inv_id)

    async def get_steps(self, inv_id: UUID) -> list:
        return await self.step_repo.get_by_investigation(inv_id)

    async def list_by_incident(self, incident_id: UUID) -> List[Investigation]:
        return await self.repo.get_by_incident(incident_id)


async def investigation_sse_stream(investigation_id: UUID) -> AsyncGenerator[str, None]:
    """
    SSE generator that streams investigation step updates in real time.
    Polls DB every 1 second for step status changes.
    """
    seen_statuses: Dict[str, str] = {}
    max_polls = 120  # 2 minutes max

    async with get_db_context() as db:
        step_repo = InvestigationStepRepository(db)
        inv_repo = InvestigationRepository(db)

        for poll_num in range(max_polls):
            steps = await step_repo.get_by_investigation(investigation_id)
            inv = await inv_repo.get_by_id(investigation_id)

            for step in steps:
                step_key = str(step.id)
                current_status = step.status

                if seen_statuses.get(step_key) != current_status:
                    seen_statuses[step_key] = current_status
                    data = {
                        "type": "step_update",
                        "step_order": step.step_order,
                        "step_name": step.step_name,
                        "step_description": step.step_description,
                        "status": current_status,
                        "confidence": step.confidence,
                        "ai_reasoning": step.ai_reasoning[:300] if step.ai_reasoning else None,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    yield f"data: {json.dumps(data)}\n\n"

            # Check if investigation is complete
            if inv and inv.status in ("completed", "failed"):
                final_data = {
                    "type": "investigation_complete",
                    "status": inv.status,
                    "root_cause": inv.root_cause[:500] if inv.root_cause else None,
                    "confidence": inv.root_cause_confidence,
                    "resolution_suggestions": inv.resolution_suggestions,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                yield f"data: {json.dumps(final_data)}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return

            await asyncio.sleep(1.0)

        # Timeout
        yield 'data: {"type": "timeout", "message": "Investigation still running"}\n\n'
