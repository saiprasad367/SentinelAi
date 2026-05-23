"""
SentinelAI — Incident Engine Service
Business logic: incident creation, file upload processing, AI summary generation.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core.events import EventType, event_bus
from modules.incident_engine.models import Incident, UploadedFile
from modules.incident_engine.parser import (
    classify_severity_from_entries,
    extract_incident_title,
    parse_file,
)
from modules.incident_engine.repository import (
    IncidentRepository,
    LogRepository,
    MetricRepository,
    UploadedFileRepository,
)
from shared.ai.openrouter import get_openrouter

logger = logging.getLogger("sentinel.incident.service")


class IncidentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.incident_repo = IncidentRepository(db)
        self.log_repo = LogRepository(db)
        self.metric_repo = MetricRepository(db)
        self.file_repo = UploadedFileRepository(db)

    async def create_incident(
        self,
        title: str,
        description: Optional[str] = None,
        severity: str = "P3",
        affected_service: Optional[str] = None,
        affected_services: Optional[List[str]] = None,
        source: str = "api",
        raw_data: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> Incident:
        """Create a new incident and trigger investigation."""
        incident = await self.incident_repo.create(
            title=title,
            description=description,
            severity=severity,
            status="detecting",
            affected_service=affected_service,
            affected_services=affected_services or [],
            source=source,
            raw_data=raw_data,
            tags=tags or [],
        )

        # Emit incident detected event (triggers investigation engine)
        await event_bus.emit(
            EventType.INCIDENT_DETECTED,
            payload={
                "incident_id": str(incident.id),
                "title": incident.title,
                "severity": incident.severity,
                "affected_service": incident.affected_service,
            },
            incident_id=str(incident.id),
        )

        logger.info(f"Incident created: {incident.id} [{severity}] {title[:60]}")
        return incident

    async def process_uploaded_file(
        self,
        filename: str,
        content: str,
        file_type: str,
    ) -> Dict[str, Any]:
        """
        Parse an uploaded log file, extract incidents, store logs.
        Returns summary of what was found.
        """
        # Record the upload
        file_record = await self.file_repo.create(
            filename=filename,
            file_type=file_type,
            file_size_bytes=len(content.encode("utf-8")),
            parsing_status="processing",
        )

        try:
            # Parse the file
            entries = parse_file(content, file_type)
            error_entries = [e for e in entries if e.is_error]

            incident_ids = []
            if error_entries:
                # Determine severity from errors
                severity = classify_severity_from_entries(entries)
                title = extract_incident_title(entries)

                # Create incident
                incident = await self.create_incident(
                    title=title,
                    description=f"Detected from uploaded file: {filename}. Found {len(error_entries)} error entries.",
                    severity=severity,
                    source="log_upload",
                    tags=["auto-detected", "log-upload"],
                )
                incident_ids.append(incident.id)

                # Store error logs linked to incident
                log_data = [
                    {
                        "incident_id": incident.id,
                        "service_name": e.service_name,
                        "level": e.level,
                        "message": e.message[:2000],
                        "timestamp": e.timestamp,
                        "raw_line": e.raw_line[:1000] if e.raw_line else None,
                        "meta_data": e.metadata,
                    }
                    for e in error_entries[:500]  # cap at 500 error lines
                ]
                await self.log_repo.bulk_create(log_data)

                # Update file record with incident link
                await self.file_repo.update(
                    file_record.id,
                    incident_id=incident.id,
                )

            # Update file record
            await self.file_repo.update(
                file_record.id,
                lines_parsed=len(entries),
                errors_found=len(error_entries),
                parsing_status="completed",
            )

            return {
                "file_id": file_record.id,
                "filename": filename,
                "file_type": file_type,
                "lines_parsed": len(entries),
                "errors_found": len(error_entries),
                "incidents_created": len(incident_ids),
                "incident_ids": incident_ids,
                "status": "completed",
            }

        except Exception as e:
            logger.error(f"File parsing failed for {filename}: {e}")
            await self.file_repo.update(file_record.id, parsing_status="failed")
            raise

    async def update_incident(self, incident_id: UUID, **kwargs) -> Optional[Incident]:
        incident = await self.incident_repo.update(incident_id, **kwargs)
        if incident:
            await event_bus.emit(
                EventType.INCIDENT_UPDATED,
                payload={"incident_id": str(incident_id), **kwargs},
                incident_id=str(incident_id),
            )
        return incident

    async def resolve_incident(self, incident_id: UUID) -> Optional[Incident]:
        incident = await self.incident_repo.update(
            incident_id,
            status="resolved",
            resolved_at=datetime.now(timezone.utc),
        )
        if incident:
            await event_bus.emit(
                EventType.INCIDENT_RESOLVED,
                payload={"incident_id": str(incident_id)},
                incident_id=str(incident_id),
            )
        return incident

    async def get_incident(self, incident_id: UUID) -> Optional[Incident]:
        return await self.incident_repo.get_by_id(incident_id)

    async def list_incidents(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Tuple[List[Incident], int]:
        return await self.incident_repo.get_all(page, page_size, status, severity)

    async def ingest_metric(
        self,
        service_name: str,
        metric_name: str,
        value: float,
        unit: Optional[str] = None,
        labels: Optional[Dict] = None,
    ) -> None:
        """Store a metric reading and emit metric updated event."""
        await self.metric_repo.create(
            service_name=service_name,
            metric_name=metric_name,
            value=value,
            unit=unit,
            labels=labels or {},
        )
        await event_bus.emit(
            EventType.METRIC_UPDATED,
            payload={
                "service_name": service_name,
                "metric_name": metric_name,
                "value": value,
            },
        )
