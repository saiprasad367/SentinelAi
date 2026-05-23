"""
SentinelAI — Incident Engine Models
Tables: incidents, logs, metrics, services, uploaded_files
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Severity(str, enum.Enum):
    P1 = "P1"   # Critical - full outage
    P2 = "P2"   # High - major degradation
    P3 = "P3"   # Medium - partial impact
    P4 = "P4"   # Low - minor issue


class IncidentStatus(str, enum.Enum):
    DETECTING = "detecting"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(SAEnum(Severity), nullable=False, default=Severity.P3)
    status = Column(SAEnum(IncidentStatus), nullable=False, default=IncidentStatus.DETECTING)

    affected_service = Column(String(200), nullable=True)
    affected_services = Column(JSON, nullable=True, default=list)  # list of service names

    # Detection metadata
    detected_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # AI analysis results
    root_cause = Column(Text, nullable=True)
    root_cause_confidence = Column(Float, nullable=True)
    ai_summary = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True, default=list)

    # Source tracking
    source = Column(String(100), nullable=True, default="api")  # api, log_upload, metric_alert
    raw_data = Column(JSON, nullable=True)

    # Relationships
    logs = relationship("Log", back_populates="incident", cascade="all, delete-orphan")
    investigations = relationship("Investigation", back_populates="incident")
    impact_assessments = relationship("ImpactAssessment", back_populates="incident")
    recommendations = relationship("Recommendation", back_populates="incident")
    replay_events = relationship("OutageReplay", back_populates="incident")

    def __repr__(self):
        return f"<Incident {self.id} [{self.severity}] {self.title[:50]}>"


class Log(Base):
    __tablename__ = "logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True)
    service_name = Column(String(200), nullable=True)
    level = Column(String(20), nullable=False, default="INFO")  # DEBUG, INFO, WARN, ERROR, FATAL
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    raw_line = Column(Text, nullable=True)
    meta_data = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    incident = relationship("Incident", back_populates="logs")


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    service_name = Column(String(200), nullable=False, index=True)
    metric_name = Column(String(200), nullable=False, index=True)  # cpu, memory, latency, error_rate, rps
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)   # percent, ms, req/s, count
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    labels = Column(JSON, nullable=True, default=dict)


class Service(Base):
    __tablename__ = "services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(200), nullable=False, unique=True, index=True)
    display_name = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    service_type = Column(String(100), nullable=True)  # api, database, cache, queue, frontend
    health_status = Column(String(50), nullable=False, default="healthy")  # healthy, degraded, down
    criticality = Column(Integer, nullable=False, default=5)  # 1-10 scale
    owner_team = Column(String(200), nullable=True)
    tags = Column(JSON, nullable=True, default=list)
    meta_data = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_service = Column(String(200), nullable=False, index=True)
    target_service = Column(String(200), nullable=False, index=True)
    dependency_type = Column(String(100), nullable=True, default="sync")  # sync, async, cache
    criticality = Column(Integer, nullable=False, default=5)
    latency_p50_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # log, json, csv, txt
    file_size_bytes = Column(Integer, nullable=True)
    lines_parsed = Column(Integer, nullable=True)
    errors_found = Column(Integer, nullable=True, default=0)
    parsing_status = Column(String(50), nullable=False, default="pending")
    storage_path = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
