"""
SentinelAI — PDF Report Engine
Generates executive incident post-mortem reports using ReportLab.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.events import EventType, event_bus
from modules.shared_models import Report

logger = logging.getLogger("sentinel.report.service")

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_report(
        self,
        incident_id: UUID,
        report_type: str = "postmortem",
    ) -> Report:
        """Generate a comprehensive PDF report for an incident."""
        from modules.incident_engine.repository import IncidentRepository
        inc_repo = IncidentRepository(self.db)
        incident = await inc_repo.get_by_id(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Create report record
        report = Report(
            incident_id=incident_id,
            title=f"Post-Mortem: {incident.title[:100]}",
            report_type=report_type,
            status="generating",
        )
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        await self.db.commit()

        # Gather data for report
        content = await self._gather_report_content(incident)

        # Generate PDF
        pdf_bytes = await self._generate_pdf(report.id, incident, content)

        # Save PDF
        pdf_path = REPORTS_DIR / f"report_{report.id}.pdf"
        pdf_path.write_bytes(pdf_bytes)

        # Update report record
        report.status = "completed"
        report.content = content
        report.pdf_path = str(pdf_path)
        report.pdf_size_bytes = len(pdf_bytes)
        report.generated_at = datetime.now(timezone.utc)
        await self.db.flush()

        await event_bus.emit(
            EventType.REPORT_GENERATED,
            payload={
                "report_id": str(report.id),
                "incident_id": str(incident_id),
                "pdf_path": str(pdf_path),
            },
        )

        return report

    async def _gather_report_content(self, incident: Any) -> Dict[str, Any]:
        """Gather all data needed for the report."""
        content: Dict[str, Any] = {
            "incident": {
                "id": str(incident.id),
                "title": incident.title,
                "severity": incident.severity,
                "status": incident.status,
                "detected_at": incident.detected_at.isoformat(),
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
                "affected_service": incident.affected_service,
                "root_cause": incident.root_cause,
                "confidence": incident.root_cause_confidence,
            }
        }

        # Get impact
        try:
            from modules.impact_engine.service import ImpactService
            impact_svc = ImpactService(self.db)
            impact = await impact_svc.get_impact(incident.id)
            if impact:
                content["impact"] = {
                    "level": impact.impact_level,
                    "affected_users": impact.affected_users,
                    "revenue_loss": impact.estimated_total_loss,
                    "blast_radius": impact.blast_radius_count,
                    "direct_services": impact.direct_services,
                }
        except Exception:
            content["impact"] = {}

        # Get recommendations
        try:
            from modules.impact_engine.service import ImpactService
            impact_svc = ImpactService(self.db)
            recs = await impact_svc.get_recommendations(incident.id)
            content["recommendations"] = [
                {"priority": r.priority, "title": r.title, "steps": r.action_steps}
                for r in recs
            ]
        except Exception:
            content["recommendations"] = []

        # Get investigation
        try:
            from modules.investigation_engine.repository import InvestigationRepository
            inv_repo = InvestigationRepository(self.db)
            invs = await inv_repo.get_by_incident(incident.id)
            if invs:
                inv = invs[0]
                content["investigation"] = {
                    "causal_chain": inv.causal_chain,
                    "ai_narrative": inv.ai_narrative,
                    "evidence": inv.evidence,
                }
        except Exception:
            content["investigation"] = {}

        # Generate AI executive summary
        try:
            from shared.ai.openrouter import get_openrouter
            ai = get_openrouter()
            summary_prompt = f"""Write a 3-paragraph executive summary for this incident post-mortem:

Incident: {incident.title}
Severity: {incident.severity}
Root Cause: {incident.root_cause or 'Under investigation'}
Impact: {content.get('impact', {}).get('level', 'Unknown')} - {content.get('impact', {}).get('affected_users', 0):,} users

Paragraph 1: What happened (technical but accessible)
Paragraph 2: Business impact and timeline  
Paragraph 3: Resolution and prevention measures

Keep it professional, 150 words per paragraph."""

            summary = await ai.complete(
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=600,
                temperature=0.2,
            )
            content["executive_summary"] = summary
        except Exception as e:
            content["executive_summary"] = f"AI summary unavailable. Incident: {incident.title}"

        return content

    async def _generate_pdf(
        self,
        report_id: UUID,
        incident: Any,
        content: Dict,
    ) -> bytes:
        """Generate PDF using ReportLab."""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor, black, white
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                HRFlowable, PageBreak,
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)

            styles = getSampleStyleSheet()
            primary = HexColor("#1e40af")
            danger = HexColor("#dc2626")
            muted = HexColor("#6b7280")

            title_style = ParagraphStyle("Title", parent=styles["Title"], textColor=primary, fontSize=24, spaceAfter=12)
            h2_style = ParagraphStyle("H2", parent=styles["Heading2"], textColor=primary, fontSize=14, spaceAfter=8)
            body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=16, spaceAfter=8)
            meta_style = ParagraphStyle("Meta", parent=styles["Normal"], fontSize=9, textColor=muted)

            elements = []

            # ── Header ──────────────────────────────────────────────────────────
            elements.append(Paragraph("SentinelAI", ParagraphStyle("Brand", parent=styles["Normal"], fontSize=11, textColor=muted, spaceAfter=4)))
            elements.append(Paragraph("INCIDENT POST-MORTEM REPORT", title_style))
            elements.append(Paragraph(incident.title, ParagraphStyle("IncTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=6)))
            elements.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Severity: {incident.severity} | Status: {incident.status}", meta_style))
            elements.append(HRFlowable(width="100%", thickness=2, color=primary))
            elements.append(Spacer(1, 12))

            # ── Executive Summary ────────────────────────────────────────────────
            elements.append(Paragraph("Executive Summary", h2_style))
            summary = content.get("executive_summary", "See incident details below.")
            elements.append(Paragraph(summary.replace("\n", "<br/>"), body_style))
            elements.append(Spacer(1, 12))

            # ── Incident Overview Table ─────────────────────────────────────────
            elements.append(Paragraph("Incident Overview", h2_style))
            inc_data = content.get("incident", {})
            overview_data = [
                ["Field", "Value"],
                ["Incident ID", str(incident.id)[:8] + "..."],
                ["Severity", incident.severity],
                ["Status", incident.status],
                ["Affected Service", incident.affected_service or "Multiple"],
                ["Detected At", incident.detected_at.strftime("%Y-%m-%d %H:%M UTC")],
                ["Resolved At", incident.resolved_at.strftime("%Y-%m-%d %H:%M UTC") if incident.resolved_at else "Ongoing"],
            ]
            table = Table(overview_data, colWidths=[2 * inch, 4 * inch])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), primary),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f8fafc"), white]),
                ("GRID", (0, 0), (-1, -1), 0.5, muted),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 16))

            # ── Root Cause ───────────────────────────────────────────────────────
            elements.append(Paragraph("Root Cause Analysis", h2_style))
            rc = incident.root_cause or "Investigation in progress."
            elements.append(Paragraph(rc[:1500].replace("\n", "<br/>"), body_style))
            if incident.root_cause_confidence:
                elements.append(Paragraph(f"<b>AI Confidence:</b> {incident.root_cause_confidence:.0%}", meta_style))
            elements.append(Spacer(1, 12))

            # ── Business Impact ──────────────────────────────────────────────────
            impact = content.get("impact", {})
            if impact:
                elements.append(Paragraph("Business Impact", h2_style))
                impact_data = [
                    ["Metric", "Value"],
                    ["Impact Level", impact.get("level", "Unknown").upper()],
                    ["Users Affected", f"{impact.get('affected_users', 0):,}"],
                    ["Estimated Revenue Loss", f"${impact.get('revenue_loss', 0):,.0f}"],
                    ["Services in Blast Radius", str(impact.get("blast_radius", 0))],
                ]
                imp_table = Table(impact_data, colWidths=[3 * inch, 3 * inch])
                imp_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), danger),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#fef2f2"), white]),
                    ("GRID", (0, 0), (-1, -1), 0.5, muted),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]))
                elements.append(imp_table)
                elements.append(Spacer(1, 12))

            # ── Recommendations ──────────────────────────────────────────────────
            recs = content.get("recommendations", [])
            if recs:
                elements.append(Paragraph("Remediation Recommendations", h2_style))
                for rec in recs:
                    elements.append(Paragraph(f"<b>{rec['priority']}. {rec['title']}</b>", body_style))
                    steps = rec.get("steps", [])
                    for step in steps:
                        elements.append(Paragraph(f"  • {step}", body_style))
                elements.append(Spacer(1, 12))

            # ── Footer ────────────────────────────────────────────────────────
            elements.append(HRFlowable(width="100%", thickness=1, color=muted))
            elements.append(Paragraph("Generated by SentinelAI — The Autonomous Reliability Engineer", meta_style))

            doc.build(elements)
            return buffer.getvalue()

        except ImportError:
            # ReportLab not installed - return simple text PDF placeholder
            logger.warning("ReportLab not installed. Generating placeholder.")
            return self._generate_text_report(incident, content)

    def _generate_text_report(self, incident: Any, content: Dict) -> bytes:
        """Simple text fallback when ReportLab unavailable."""
        lines = [
            "SentinelAI — Incident Post-Mortem Report",
            "=" * 60,
            f"Title: {incident.title}",
            f"Severity: {incident.severity}",
            f"Status: {incident.status}",
            f"Root Cause: {incident.root_cause or 'Under investigation'}",
            "",
            "Executive Summary:",
            content.get("executive_summary", "N/A"),
        ]
        return "\n".join(lines).encode("utf-8")

    async def get_report(self, report_id: UUID) -> Optional[Report]:
        return await self.db.get(Report, report_id)

    async def list_reports(self, incident_id: Optional[UUID] = None) -> list:
        q = select(Report).order_by(desc(Report.created_at))
        if incident_id:
            q = q.where(Report.incident_id == incident_id)
        result = await self.db.execute(q)
        return result.scalars().all()
