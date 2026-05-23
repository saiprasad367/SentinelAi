"""SentinelAI — Report Engine Controller"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.report_engine.service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


class ReportRequest(BaseModel):
    incident_id: UUID
    report_type: str = "postmortem"


@router.post("/generate", status_code=201)
async def generate_report(payload: ReportRequest, db: AsyncSession = Depends(get_db)):
    """Generate an executive PDF post-mortem report."""
    svc = ReportService(db)
    try:
        report = await svc.generate_report(payload.incident_id, payload.report_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "report_id": str(report.id),
        "incident_id": str(payload.incident_id),
        "title": report.title,
        "status": report.status,
        "pdf_size_bytes": report.pdf_size_bytes,
        "download_url": f"/api/v1/reports/{report.id}/download",
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }


@router.get("/{report_id}/download")
async def download_report(report_id: UUID, db: AsyncSession = Depends(get_db)):
    """Download the PDF report."""
    svc = ReportService(db)
    report = await svc.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "completed" or not report.pdf_path:
        raise HTTPException(status_code=202, detail="Report is still generating")
    pdf_path = Path(report.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"sentinelai_report_{report_id}.pdf",
    )


@router.get("/{report_id}")
async def get_report(report_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get report metadata and content."""
    svc = ReportService(db)
    report = await svc.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": str(report.id),
        "incident_id": str(report.incident_id),
        "title": report.title,
        "status": report.status,
        "content": report.content,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }


@router.get("/incident/{incident_id}")
async def list_incident_reports(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    """List all reports for an incident."""
    svc = ReportService(db)
    reports = await svc.list_reports(incident_id)
    return [
        {"id": str(r.id), "title": r.title, "status": r.status, "created_at": r.created_at.isoformat()}
        for r in reports
    ]
