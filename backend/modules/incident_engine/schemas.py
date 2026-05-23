"""
SentinelAI — Incident Engine Schemas (Pydantic v2)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "P3"
    affected_service: Optional[str] = None
    affected_services: List[str] = Field(default_factory=list)
    source: str = "api"
    raw_data: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    root_cause: Optional[str] = None
    root_cause_confidence: Optional[float] = None


class IncidentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    affected_service: Optional[str] = None
    affected_services: List[str] = Field(default_factory=list)
    root_cause: Optional[str] = None
    root_cause_confidence: Optional[float] = None
    ai_summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class LogCreate(BaseModel):
    incident_id: Optional[UUID] = None
    service_name: Optional[str] = None
    level: str = "INFO"
    message: str
    timestamp: Optional[datetime] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata", serialization_alias="metadata")


class LogResponse(BaseModel):
    model_config = {"from_attributes": True, "populate_by_name": True}

    id: UUID
    incident_id: Optional[UUID] = None
    service_name: Optional[str] = None
    level: str
    message: str
    timestamp: datetime
    meta_data: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata", serialization_alias="metadata")


class MetricCreate(BaseModel):
    service_name: str
    metric_name: str
    value: float
    unit: Optional[str] = None
    labels: Dict[str, Any] = Field(default_factory=dict)


class MetricResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    service_name: str
    metric_name: str
    value: float
    unit: Optional[str] = None
    timestamp: datetime


class FileUploadResponse(BaseModel):
    file_id: UUID
    filename: str
    file_type: str
    lines_parsed: int
    errors_found: int
    incidents_created: int
    incident_ids: List[UUID] = Field(default_factory=list)
    status: str


class IncidentListResponse(BaseModel):
    incidents: List[IncidentResponse]
    total: int
    page: int
    page_size: int
