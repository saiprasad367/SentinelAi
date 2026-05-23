"""
SentinelAI — Incident Engine Repository
Database access layer for incidents, logs, metrics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.incident_engine.models import Incident, Log, Metric, Service, UploadedFile

logger = logging.getLogger("sentinel.incident.repository")


class IncidentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **kwargs) -> Incident:
        incident = Incident(**kwargs)
        self.db.add(incident)
        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def get_by_id(self, incident_id: UUID) -> Optional[Incident]:
        result = await self.db.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> tuple[List[Incident], int]:
        q = select(Incident)
        if status:
            q = q.where(Incident.status == status)
        if severity:
            q = q.where(Incident.severity == severity)
        q = q.order_by(desc(Incident.created_at))

        count_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = count_result.scalar_one()

        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(q)
        return result.scalars().all(), total

    async def update(self, incident_id: UUID, **kwargs) -> Optional[Incident]:
        incident = await self.get_by_id(incident_id)
        if not incident:
            return None
        for k, v in kwargs.items():
            setattr(incident, k, v)
        incident.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def get_recent(self, limit: int = 10) -> List[Incident]:
        result = await self.db.execute(
            select(Incident).order_by(desc(Incident.created_at)).limit(limit)
        )
        return result.scalars().all()

    async def count_by_severity(self) -> dict:
        result = await self.db.execute(
            select(Incident.severity, func.count(Incident.id))
            .group_by(Incident.severity)
        )
        return {row[0]: row[1] for row in result.fetchall()}


class LogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def bulk_create(self, log_data: List[dict]) -> int:
        logs = [Log(**d) for d in log_data]
        self.db.add_all(logs)
        await self.db.flush()
        return len(logs)

    async def get_by_incident(self, incident_id: UUID, limit: int = 100) -> List[Log]:
        result = await self.db.execute(
            select(Log)
            .where(Log.incident_id == incident_id)
            .order_by(Log.timestamp)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_errors(self, incident_id: UUID) -> List[Log]:
        result = await self.db.execute(
            select(Log)
            .where(Log.incident_id == incident_id, Log.level.in_(["ERROR", "FATAL"]))
            .order_by(Log.timestamp)
        )
        return result.scalars().all()


class MetricRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **kwargs) -> Metric:
        metric = Metric(**kwargs)
        self.db.add(metric)
        await self.db.flush()
        return metric

    async def bulk_create(self, metric_data: List[dict]) -> int:
        metrics = [Metric(**d) for d in metric_data]
        self.db.add_all(metrics)
        await self.db.flush()
        return len(metrics)

    async def get_latest_for_service(self, service_name: str, metric_name: str, limit: int = 60) -> List[Metric]:
        result = await self.db.execute(
            select(Metric)
            .where(Metric.service_name == service_name, Metric.metric_name == metric_name)
            .order_by(desc(Metric.timestamp))
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def get_all_services_latest(self) -> List[Metric]:
        """Get latest metric value per service per metric_name."""
        subq = (
            select(
                Metric.service_name,
                Metric.metric_name,
                func.max(Metric.timestamp).label("max_ts"),
            )
            .group_by(Metric.service_name, Metric.metric_name)
            .subquery()
        )
        result = await self.db.execute(
            select(Metric).join(
                subq,
                (Metric.service_name == subq.c.service_name)
                & (Metric.metric_name == subq.c.metric_name)
                & (Metric.timestamp == subq.c.max_ts),
            )
        )
        return result.scalars().all()


class UploadedFileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **kwargs) -> UploadedFile:
        f = UploadedFile(**kwargs)
        self.db.add(f)
        await self.db.flush()
        await self.db.refresh(f)
        return f

    async def update(self, file_id: UUID, **kwargs) -> Optional[UploadedFile]:
        result = await self.db.execute(select(UploadedFile).where(UploadedFile.id == file_id))
        f = result.scalar_one_or_none()
        if not f:
            return None
        for k, v in kwargs.items():
            setattr(f, k, v)
        await self.db.flush()
        return f
