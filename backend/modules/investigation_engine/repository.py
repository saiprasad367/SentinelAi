"""
SentinelAI — Investigation Engine Repository
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.investigation_engine.models import Investigation, InvestigationStep

logger = logging.getLogger("sentinel.investigation.repository")


class InvestigationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **kwargs) -> Investigation:
        inv = Investigation(**kwargs)
        self.db.add(inv)
        await self.db.flush()
        await self.db.refresh(inv)
        return inv

    async def get_by_id(self, inv_id: UUID) -> Optional[Investigation]:
        result = await self.db.execute(
            select(Investigation)
            .where(Investigation.id == inv_id)
            .options(selectinload(Investigation.steps))
        )
        return result.scalar_one_or_none()

    async def get_by_incident(self, incident_id: UUID) -> List[Investigation]:
        result = await self.db.execute(
            select(Investigation)
            .where(Investigation.incident_id == incident_id)
            .order_by(desc(Investigation.created_at))
        )
        return result.scalars().all()

    async def update(self, inv_id: UUID, **kwargs) -> Optional[Investigation]:
        inv = await self.db.get(Investigation, inv_id)
        if not inv:
            return None
        for k, v in kwargs.items():
            setattr(inv, k, v)
        await self.db.flush()
        return inv


class InvestigationStepRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **kwargs) -> InvestigationStep:
        step = InvestigationStep(**kwargs)
        self.db.add(step)
        await self.db.flush()
        await self.db.refresh(step)
        return step

    async def get_by_investigation(self, inv_id: UUID) -> List[InvestigationStep]:
        result = await self.db.execute(
            select(InvestigationStep)
            .where(InvestigationStep.investigation_id == inv_id)
            .order_by(InvestigationStep.step_order)
        )
        return result.scalars().all()

    async def update(self, step_id: UUID, **kwargs) -> Optional[InvestigationStep]:
        step = await self.db.get(InvestigationStep, step_id)
        if not step:
            return None
        for k, v in kwargs.items():
            setattr(step, k, v)
        if "status" in kwargs and kwargs["status"] == "completed":
            step.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return step
