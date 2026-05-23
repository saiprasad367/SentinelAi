"""
SentinelAI — Investigation Engine Models
Tables: investigations, investigation_steps
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, Enum as SAEnum, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class InvestigationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(SAEnum(InvestigationStatus), nullable=False, default=InvestigationStatus.PENDING)

    # Results
    root_cause = Column(Text, nullable=True)
    root_cause_confidence = Column(Float, nullable=True)
    causal_chain = Column(JSON, nullable=True, default=list)   # ordered list of cause events
    evidence = Column(JSON, nullable=True, default=list)
    affected_services = Column(JSON, nullable=True, default=list)
    resolution_suggestions = Column(JSON, nullable=True, default=list)
    ai_narrative = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Model used
    model_used = Column(String(200), nullable=True)

    incident = relationship("Incident", back_populates="investigations")
    steps = relationship("InvestigationStep", back_populates="investigation", order_by="InvestigationStep.step_order")


class InvestigationStep(Base):
    __tablename__ = "investigation_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    investigation_id = Column(UUID(as_uuid=True), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    step_name = Column(String(300), nullable=False)
    step_description = Column(Text, nullable=True)
    status = Column(SAEnum(StepStatus), nullable=False, default=StepStatus.PENDING)

    # Step data
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    evidence_found = Column(JSON, nullable=True, default=list)
    confidence = Column(Float, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Float, nullable=True)

    investigation = relationship("Investigation", back_populates="steps")
