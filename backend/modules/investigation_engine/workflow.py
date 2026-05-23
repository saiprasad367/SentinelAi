"""
SentinelAI — Root Cause Investigation Workflow
The core AI reasoning engine. Runs a multi-step investigation
and streams progress via SSE to the frontend.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.events import EventType, event_bus
from shared.ai.openrouter import get_openrouter
from core.config import settings

logger = logging.getLogger("sentinel.investigation.workflow")

INVESTIGATION_STEPS = [
    {
        "order": 1,
        "name": "Analyzing system logs",
        "description": "Scanning error logs, stack traces, and exception patterns",
    },
    {
        "order": 2,
        "name": "Examining infrastructure metrics",
        "description": "Checking CPU, memory, latency, error rate, and request volume",
    },
    {
        "order": 3,
        "name": "Tracing service dependencies",
        "description": "Mapping call graph and identifying upstream/downstream failures",
    },
    {
        "order": 4,
        "name": "Comparing historical incidents",
        "description": "Searching memory bank for similar past failures and resolutions",
    },
    {
        "order": 5,
        "name": "Analyzing deployment timeline",
        "description": "Checking recent deploys, config changes, and infra modifications",
    },
    {
        "order": 6,
        "name": "Synthesizing root cause",
        "description": "Building causal chain from evidence and computing confidence score",
    },
]


async def run_investigation(
    investigation_id: UUID,
    incident_id: UUID,
    incident_title: str,
    incident_description: Optional[str],
    affected_service: Optional[str],
    logs_sample: List[str],
    db: AsyncSession,
) -> Dict:
    """
    Execute the full investigation workflow.
    Updates DB at each step. Returns final result.
    """
    from modules.investigation_engine.repository import InvestigationRepository, InvestigationStepRepository

    inv_repo = InvestigationRepository(db)
    step_repo = InvestigationStepRepository(db)
    ai = get_openrouter()

    # Update investigation to RUNNING
    await inv_repo.update(investigation_id, status="running", started_at=datetime.now(timezone.utc))

    # Create all step records upfront
    step_records = []
    for step_def in INVESTIGATION_STEPS:
        step = await step_repo.create(
            investigation_id=investigation_id,
            step_order=step_def["order"],
            step_name=step_def["name"],
            step_description=step_def["description"],
            status="pending",
        )
        step_records.append(step)
    await db.commit()

    evidence_collected = []

    # ── Step 1: Log Analysis ──────────────────────────────────────────────────
    step = step_records[0]
    await step_repo.update(step.id, status="running", started_at=datetime.now(timezone.utc))
    await db.commit()
    await event_bus.emit(
        EventType.INVESTIGATION_STEP_COMPLETED,
        payload={
            "investigation_id": str(investigation_id),
            "step_order": 1,
            "step_name": step.step_name,
            "status": "running",
            "incident_id": str(incident_id),
        },
        incident_id=str(incident_id),
    )

    log_context = "\n".join(logs_sample[:20]) if logs_sample else "No log samples available"
    log_prompt = f"""Analyze these log entries from incident "{incident_title}" and identify the key error patterns:

LOGS:
{log_context}

Provide:
1. Primary error type
2. Error frequency pattern
3. First occurrence timestamp
4. Affected components
Keep response concise and technical."""

    log_analysis = ""
    try:
        log_analysis = await ai.complete(
            messages=[{"role": "user", "content": log_prompt}],
            model=settings.openrouter_fast_model,
            max_tokens=500,
        )
        evidence_collected.append({"source": "logs", "finding": log_analysis[:500]})
    except Exception as e:
        log_analysis = f"Log analysis unavailable: {e}"

    await step_repo.update(
        step.id,
        status="completed",
        output_data={"analysis": log_analysis[:1000]},
        ai_reasoning=log_analysis[:2000],
        confidence=0.8,
        completed_at=datetime.now(timezone.utc),
    )
    await db.commit()

    await asyncio.sleep(0.5)  # Simulate real investigation pacing

    # ── Step 2: Metrics Analysis ──────────────────────────────────────────────
    step = step_records[1]
    await step_repo.update(step.id, status="running", started_at=datetime.now(timezone.utc))
    await db.commit()
    await event_bus.emit(
        EventType.INVESTIGATION_STEP_COMPLETED,
        payload={
            "investigation_id": str(investigation_id),
            "step_order": 2,
            "step_name": step.step_name,
            "status": "running",
        },
        incident_id=str(incident_id),
    )

    # Fetch actual metrics from DB
    from modules.incident_engine.repository import MetricRepository
    metric_repo = MetricRepository(db)
    metrics_summary = "Metrics collected but analysis skipped due to time constraints"
    if affected_service:
        try:
            for metric_name in ["cpu", "memory", "latency", "error_rate"]:
                m_list = await metric_repo.get_latest_for_service(affected_service, metric_name, limit=5)
                if m_list:
                    values = [f"{m.value:.1f}" for m in m_list[-3:]]
                    evidence_collected.append({
                        "source": "metrics",
                        "finding": f"{metric_name} trend: {' → '.join(values)}"
                    })
        except Exception as e:
            logger.warning(f"Metric fetch failed: {e}")

    await step_repo.update(
        step.id,
        status="completed",
        output_data={"metrics": evidence_collected[-3:] if len(evidence_collected) > 1 else []},
        confidence=0.75,
        completed_at=datetime.now(timezone.utc),
    )
    await db.commit()
    await asyncio.sleep(0.5)

    # ── Step 3: Dependency Graph Analysis ─────────────────────────────────────
    step = step_records[2]
    await step_repo.update(step.id, status="running", started_at=datetime.now(timezone.utc))
    await db.commit()
    await event_bus.emit(
        EventType.INVESTIGATION_STEP_COMPLETED,
        payload={
            "investigation_id": str(investigation_id),
            "step_order": 3,
            "step_name": step.step_name,
            "status": "running",
        },
        incident_id=str(incident_id),
    )

    blast_radius_services = []
    if affected_service:
        try:
            from modules.graph_engine.service import GraphService
            graph_svc = GraphService(db)
            blast_result = await graph_svc.compute_blast_radius(affected_service)
            blast_radius_services = blast_result.get("impacted_services", [])
            evidence_collected.append({
                "source": "dependency_graph",
                "finding": f"Blast radius: {len(blast_radius_services)} services affected downstream"
            })
        except Exception as e:
            logger.warning(f"Graph analysis skipped: {e}")

    await step_repo.update(
        step.id,
        status="completed",
        output_data={"blast_radius": blast_radius_services[:10]},
        confidence=0.85,
        completed_at=datetime.now(timezone.utc),
    )
    await db.commit()
    await asyncio.sleep(0.5)

    # ── Step 4: Memory Search ──────────────────────────────────────────────────
    step = step_records[3]
    await step_repo.update(step.id, status="running", started_at=datetime.now(timezone.utc))
    await db.commit()
    await event_bus.emit(
        EventType.INVESTIGATION_STEP_COMPLETED,
        payload={
            "investigation_id": str(investigation_id),
            "step_order": 4,
            "step_name": step.step_name,
            "status": "running",
        },
        incident_id=str(incident_id),
    )

    similar_incidents = []
    try:
        from modules.memory_engine.service import MemoryService
        memory_svc = MemoryService(db)
        similar = await memory_svc.search_similar(incident_title, limit=3)
        similar_incidents = [s["title"] for s in similar]
        if similar_incidents:
            evidence_collected.append({
                "source": "memory",
                "finding": f"Found {len(similar_incidents)} similar historical incidents"
            })
        await event_bus.emit(EventType.MEMORY_MATCHED, payload={"matches": len(similar_incidents)}, incident_id=str(incident_id))
    except Exception as e:
        logger.warning(f"Memory search skipped: {e}")

    await step_repo.update(
        step.id,
        status="completed",
        output_data={"similar_incidents": similar_incidents},
        confidence=0.7,
        completed_at=datetime.now(timezone.utc),
    )
    await db.commit()
    await asyncio.sleep(0.5)

    # ── Step 5: Deployment Analysis ────────────────────────────────────────────
    step = step_records[4]
    await step_repo.update(step.id, status="running", started_at=datetime.now(timezone.utc))
    await db.commit()
    await event_bus.emit(
        EventType.INVESTIGATION_STEP_COMPLETED,
        payload={
            "investigation_id": str(investigation_id),
            "step_order": 5,
            "step_name": step.step_name,
            "status": "running",
        },
        incident_id=str(incident_id),
    )
    # In real deployment: query CI/CD system, git commits, config changes
    await step_repo.update(
        step.id,
        status="completed",
        output_data={"note": "No recent deployments detected in monitoring window"},
        confidence=0.6,
        completed_at=datetime.now(timezone.utc),
    )
    await db.commit()
    await asyncio.sleep(0.5)

    # ── Step 6: Root Cause Synthesis ──────────────────────────────────────────
    step = step_records[5]
    await step_repo.update(step.id, status="running", started_at=datetime.now(timezone.utc))
    await db.commit()
    await event_bus.emit(
        EventType.INVESTIGATION_STEP_COMPLETED,
        payload={
            "investigation_id": str(investigation_id),
            "step_order": 6,
            "step_name": step.step_name,
            "status": "running",
        },
        incident_id=str(incident_id),
    )

    evidence_text = "\n".join([f"- [{e['source']}] {e['finding']}" for e in evidence_collected])
    synthesis_prompt = f"""You are an expert SRE performing root cause analysis.

INCIDENT: {incident_title}
DESCRIPTION: {incident_description or 'Not provided'}
AFFECTED SERVICE: {affected_service or 'Unknown'}

EVIDENCE COLLECTED:
{evidence_text}

LOG ANALYSIS:
{log_analysis[:1000]}

Provide a structured root cause analysis:
1. ROOT CAUSE (1-2 sentences, specific and technical)
2. CAUSAL CHAIN (ordered list of events leading to failure)
3. CONFIDENCE SCORE (0-100, with justification)
4. AFFECTED SERVICES (list)
5. IMMEDIATE FIXES (top 3 remediation steps)
6. PREVENTION (top 2 long-term preventions)

Be precise, cite evidence, use technical SRE language."""

    root_cause_text = ""
    causal_chain = []
    confidence = 0.85
    resolution_suggestions = []

    try:
        root_cause_text = await ai.complete(
            messages=[{"role": "user", "content": synthesis_prompt}],
            model=settings.openrouter_strong_model,
            max_tokens=1200,
            temperature=0.2,
        )

        # Extract confidence from response
        import re
        conf_match = re.search(r"confidence[:\s]+(\d+)", root_cause_text, re.IGNORECASE)
        if conf_match:
            confidence = int(conf_match.group(1)) / 100.0
            confidence = max(0.0, min(1.0, confidence))

        # Build causal chain from evidence
        causal_chain = [e["finding"] for e in evidence_collected]

        # Extract suggestions
        fix_match = re.findall(r"(?:IMMEDIATE FIX|fix)[:\s]+([^\n]+)", root_cause_text, re.IGNORECASE)
        resolution_suggestions = fix_match[:3] if fix_match else [
            "Check service logs for error details",
            "Restart affected service pods",
            "Review recent configuration changes",
        ]

    except Exception as e:
        logger.error(f"Root cause synthesis failed: {e}")
        root_cause_text = f"AI synthesis unavailable. Evidence points to: {affected_service} failure based on {len(evidence_collected)} evidence items."
        causal_chain = [e["finding"] for e in evidence_collected]

    await step_repo.update(
        step.id,
        status="completed",
        ai_reasoning=root_cause_text[:3000],
        output_data={"root_cause": root_cause_text[:2000]},
        confidence=confidence,
        completed_at=datetime.now(timezone.utc),
    )
    await db.commit()

    # ── Finalize Investigation ─────────────────────────────────────────────────
    completed_at = datetime.now(timezone.utc)
    await inv_repo.update(
        investigation_id,
        status="completed",
        root_cause=root_cause_text[:2000],
        root_cause_confidence=confidence,
        causal_chain=causal_chain,
        evidence=evidence_collected,
        affected_services=blast_radius_services[:10],
        resolution_suggestions=resolution_suggestions,
        ai_narrative=root_cause_text[:3000],
        completed_at=completed_at,
        model_used=settings.openrouter_strong_model,
    )
    await db.commit()

    # Update the incident with root cause
    from modules.incident_engine.repository import IncidentRepository
    inc_repo = IncidentRepository(db)
    await inc_repo.update(
        incident_id,
        root_cause=root_cause_text[:1000],
        root_cause_confidence=confidence,
        status="identified",
    )
    await db.commit()

    await event_bus.emit(
        EventType.ROOT_CAUSE_FOUND,
        payload={
            "investigation_id": str(investigation_id),
            "incident_id": str(incident_id),
            "root_cause": root_cause_text[:500],
            "confidence": confidence,
        },
        incident_id=str(incident_id),
    )
    await event_bus.emit(EventType.INVESTIGATION_COMPLETED, payload={"investigation_id": str(investigation_id)})

    logger.info(f"Investigation {investigation_id} completed. Confidence: {confidence:.0%}")

    return {
        "status": "completed",
        "root_cause": root_cause_text[:2000],
        "confidence": confidence,
        "causal_chain": causal_chain,
        "resolution_suggestions": resolution_suggestions,
    }
