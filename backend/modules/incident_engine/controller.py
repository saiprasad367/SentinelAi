"""
SentinelAI — Incident Engine Controller (FastAPI Router)
/api/v1/incidents - all incident CRUD + file upload
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.incident_engine.schemas import (
    FileUploadResponse,
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    IncidentUpdate,
    LogResponse,
    MetricCreate,
    MetricResponse,
)
from modules.incident_engine.service import IncidentService

logger = logging.getLogger("sentinel.incident.controller")
router = APIRouter(prefix="/incidents", tags=["Incidents"])

SUPPORTED_TYPES = {"log", "txt", "json", "jsonl", "csv"}
MAX_FILE_SIZE_MB = 50


@router.post("/", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(payload: IncidentCreate, db: AsyncSession = Depends(get_db)):
    """Create a new incident manually."""
    svc = IncidentService(db)
    incident = await svc.create_incident(
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        affected_service=payload.affected_service,
        affected_services=payload.affected_services,
        source=payload.source,
        raw_data=payload.raw_data,
        tags=payload.tags,
    )
    return incident


@router.get("/", response_model=IncidentListResponse)
async def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all incidents with pagination and filtering."""
    svc = IncidentService(db)
    incidents, total = await svc.list_incidents(page, page_size, status, severity)
    return IncidentListResponse(
        incidents=incidents,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific incident by ID."""
    svc = IncidentService(db)
    incident = await svc.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incident


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: UUID,
    payload: IncidentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update incident fields."""
    svc = IncidentService(db)
    update_data = payload.model_dump(exclude_none=True)
    incident = await svc.update_incident(incident_id, **update_data)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incident


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mark incident as resolved."""
    svc = IncidentService(db)
    incident = await svc.resolve_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incident


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_log_file(
    file: UploadFile = File(..., description="Log file to analyze (.log, .txt, .json, .csv)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a log file for automatic incident detection.
    Supported formats: .log, .txt, .json, .jsonl, .csv
    Max size: 50MB
    """
    # Validate file type
    suffix = (file.filename or "").rsplit(".", 1)[-1].lower()
    if suffix not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{suffix}. Supported: {SUPPORTED_TYPES}",
        )

    # Read content
    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max: {MAX_FILE_SIZE_MB}MB")

    try:
        content = raw.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode file as UTF-8")

    svc = IncidentService(db)
    result = await svc.process_uploaded_file(
        filename=file.filename or "unknown",
        content=content,
        file_type=suffix,
    )
    return FileUploadResponse(**result)


@router.post("/{incident_id}/metrics", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
async def ingest_metric(
    incident_id: UUID,
    payload: MetricCreate,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a metric reading for a service."""
    svc = IncidentService(db)
    await svc.ingest_metric(
        service_name=payload.service_name,
        metric_name=payload.metric_name,
        value=payload.value,
        unit=payload.unit,
        labels=payload.labels,
    )
    from modules.incident_engine.repository import MetricRepository
    repo = MetricRepository(db)
    metrics = await repo.get_latest_for_service(payload.service_name, payload.metric_name, limit=1)
    return metrics[0] if metrics else {"service_name": payload.service_name, "metric_name": payload.metric_name, "value": payload.value}


@router.post("/metrics/batch", status_code=status.HTTP_201_CREATED)
async def ingest_metrics_batch(
    metrics: list[MetricCreate],
    db: AsyncSession = Depends(get_db),
):
    """Batch ingest multiple metric readings."""
    svc = IncidentService(db)
    for m in metrics:
        await svc.ingest_metric(
            service_name=m.service_name,
            metric_name=m.metric_name,
            value=m.value,
            unit=m.unit,
            labels=m.labels,
        )
    return {"ingested": len(metrics)}
