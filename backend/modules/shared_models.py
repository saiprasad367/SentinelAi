"""
SentinelAI — All Remaining Module Models
prediction_engine, memory_engine, impact_engine, graph_engine,
chat_engine, report_engine, analytics_engine, replay_engine
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Float,
    ForeignKey, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base

try:
    from pgvector.sqlalchemy import Vector
    VECTOR_AVAILABLE = True
except ImportError:
    VECTOR_AVAILABLE = False
    Vector = None


def utcnow():
    return datetime.now(timezone.utc)


# ─── Prediction Engine ────────────────────────────────────────────────────────

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    service_name = Column(String(200), nullable=False, index=True)
    metric_name = Column(String(200), nullable=False)

    # Forecast
    outage_probability = Column(Float, nullable=False)  # 0.0 - 1.0
    confidence = Column(Float, nullable=False)           # 0.0 - 1.0
    risk_score = Column(Float, nullable=False)           # 0-100
    predicted_outage_time = Column(DateTime(timezone=True), nullable=True)
    time_to_failure_minutes = Column(Float, nullable=True)

    # Method used
    algorithm = Column(String(100), nullable=False, default="prophet")  # prophet, linear, moving_avg, anomaly
    forecast_horizon_minutes = Column(Integer, nullable=False, default=30)
    model_metadata = Column(JSON, nullable=True)

    # Input snapshot
    current_value = Column(Float, nullable=True)
    baseline_value = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


# ─── Memory Engine ────────────────────────────────────────────────────────────

class IncidentMemory(Base):
    __tablename__ = "incident_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    affected_services = Column(JSON, nullable=True, default=list)
    tags = Column(JSON, nullable=True, default=list)
    severity = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Embedding(Base):
    """pgvector embedding storage for semantic similarity search."""
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_type = Column(String(100), nullable=False, index=True)  # incident, memory, log
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    text_content = Column(Text, nullable=False)
    # Store as JSON array if pgvector not available, or use Vector column
    embedding_json = Column(JSON, nullable=True)  # fallback
    model_name = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


# ─── Impact Engine ────────────────────────────────────────────────────────────

class ImpactAssessment(Base):
    __tablename__ = "impact_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)

    impact_level = Column(String(50), nullable=False)   # critical, high, medium, low
    urgency_score = Column(Float, nullable=False)         # 0-100
    severity_score = Column(Float, nullable=False)        # 0-100
    business_criticality_score = Column(Float, nullable=False)  # 0-100

    affected_users = Column(Integer, nullable=True)
    affected_percentage = Column(Float, nullable=True)    # % of total users
    revenue_loss_per_minute = Column(Float, nullable=True)  # USD
    estimated_total_loss = Column(Float, nullable=True)   # USD
    duration_minutes = Column(Float, nullable=True)

    direct_services = Column(JSON, nullable=True, default=list)
    indirect_services = Column(JSON, nullable=True, default=list)
    blast_radius_count = Column(Integer, nullable=True, default=0)

    ai_impact_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    incident = relationship("Incident", back_populates="impact_assessments")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=1)   # 1=highest
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    action_steps = Column(JSON, nullable=True, default=list)
    expected_recovery_minutes = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String(100), nullable=True)  # ai, historical, playbook
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    incident = relationship("Incident", back_populates="recommendations")


# ─── Graph Engine ─────────────────────────────────────────────────────────────

class ArchitectureNode(Base):
    __tablename__ = "architecture_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    node_id = Column(String(200), nullable=False, unique=True, index=True)  # e.g., "payment-api"
    label = Column(String(300), nullable=False)
    node_type = Column(String(100), nullable=False, default="service")  # service, database, cache, queue, external
    health_status = Column(String(50), nullable=False, default="healthy")
    criticality = Column(Integer, nullable=False, default=5)  # 1-10
    meta_data = Column(JSON, nullable=True, default=dict)
    position_x = Column(Float, nullable=True)
    position_y = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ArchitectureEdge(Base):
    __tablename__ = "architecture_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_node_id = Column(String(200), nullable=False, index=True)
    target_node_id = Column(String(200), nullable=False, index=True)
    edge_type = Column(String(100), nullable=False, default="depends_on")
    weight = Column(Float, nullable=False, default=1.0)
    latency_ms = Column(Float, nullable=True)
    meta_data = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


# ─── Chat Engine ──────────────────────────────────────────────────────────────

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(500), nullable=True)
    model_used = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)   # user, assistant, system
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True, default=list)  # source references
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    session = relationship("ChatSession", back_populates="messages")


# ─── Report Engine ────────────────────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    report_type = Column(String(100), nullable=False, default="postmortem")  # postmortem, executive, technical
    status = Column(String(50), nullable=False, default="generating")
    content = Column(JSON, nullable=True)        # structured report sections
    pdf_path = Column(String(1000), nullable=True)
    pdf_size_bytes = Column(Integer, nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


# ─── Analytics Engine ────────────────────────────────────────────────────────

class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    total_incidents = Column(Integer, nullable=False, default=0)
    incidents_p1 = Column(Integer, nullable=False, default=0)
    incidents_p2 = Column(Integer, nullable=False, default=0)
    incidents_p3 = Column(Integer, nullable=False, default=0)
    incidents_p4 = Column(Integer, nullable=False, default=0)

    resolved_incidents = Column(Integer, nullable=False, default=0)
    avg_mttr_minutes = Column(Float, nullable=True)   # Mean Time To Resolve
    avg_mtbf_hours = Column(Float, nullable=True)     # Mean Time Between Failures

    prediction_accuracy = Column(Float, nullable=True)  # % of predictions that were correct
    top_failing_service = Column(String(200), nullable=True)
    trend_data = Column(JSON, nullable=True, default=dict)


# ─── Replay Engine ────────────────────────────────────────────────────────────

class OutageReplay(Base):
    __tablename__ = "outage_replays"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(200), nullable=False)   # healthy, latency_spike, resource_exhaustion, failure, recovery
    event_name = Column(String(500), nullable=False)
    event_detail = Column(Text, nullable=True)
    affected_service = Column(String(200), nullable=True)
    metric_snapshot = Column(JSON, nullable=True, default=dict)
    sequence_order = Column(Integer, nullable=False)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    incident = relationship("Incident", back_populates="replay_events")


class EventStream(Base):
    """Stores all system events for audit and replay."""
    __tablename__ = "event_streams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type = Column(String(200), nullable=False, index=True)
    incident_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
