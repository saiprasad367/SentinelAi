"""
SentinelAI — Prediction Engine Controller
/api/v1/predictions
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.prediction_engine.service import PredictionService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


class MetricPayload(BaseModel):
    service_name: str
    metric_name: str
    horizon_minutes: int = 30


@router.get("/latest")
async def get_latest_predictions(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get most recent predictions across all services."""
    svc = PredictionService(db)
    preds = await svc.get_latest_predictions(limit)
    return [
        {
            "id": str(p.id),
            "service_name": p.service_name,
            "metric_name": p.metric_name,
            "outage_probability": p.outage_probability,
            "risk_score": p.risk_score,
            "confidence": p.confidence,
            "algorithm": p.algorithm,
            "current_value": p.current_value,
            "time_to_failure_minutes": p.time_to_failure_minutes,
            "predicted_outage_time": p.predicted_outage_time.isoformat() if p.predicted_outage_time else None,
            "created_at": p.created_at.isoformat(),
        }
        for p in preds
    ]


@router.post("/scan")
async def trigger_prediction_scan(db: AsyncSession = Depends(get_db)):
    """Manually trigger a prediction scan across all services."""
    svc = PredictionService(db)
    results = await svc.run_prediction_scan()
    return {"predictions_generated": len(results), "results": results[:10]}


@router.post("/predict")
async def predict_for_metric(payload: MetricPayload, db: AsyncSession = Depends(get_db)):
    """Generate prediction for a specific service + metric combination."""
    svc = PredictionService(db)
    result = await svc.predict_for_metric(
        payload.service_name,
        payload.metric_name,
        payload.horizon_minutes,
    )
    if not result:
        return {"message": "Insufficient data for prediction (need at least 3 data points)"}
    return result


@router.get("/service/{service_name}")
async def get_service_predictions(service_name: str, db: AsyncSession = Depends(get_db)):
    """Get all predictions for a specific service."""
    svc = PredictionService(db)
    preds = await svc.get_predictions_for_service(service_name)
    return [
        {
            "metric_name": p.metric_name,
            "outage_probability": p.outage_probability,
            "risk_score": p.risk_score,
            "algorithm": p.algorithm,
            "created_at": p.created_at.isoformat(),
        }
        for p in preds
    ]
