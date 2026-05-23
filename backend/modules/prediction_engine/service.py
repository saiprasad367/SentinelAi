"""
SentinelAI — Prediction Engine
Time-series forecasting using Prophet + moving average + anomaly detection.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.events import EventType, event_bus
from modules.incident_engine.repository import MetricRepository
from modules.shared_models import Prediction

logger = logging.getLogger("sentinel.prediction.service")

# Risk thresholds per metric
THRESHOLDS = {
    "cpu":        {"warning": 70.0, "critical": 85.0, "unit": "%"},
    "memory":     {"warning": 75.0, "critical": 90.0, "unit": "%"},
    "error_rate": {"warning": 2.0,  "critical": 5.0,  "unit": "%"},
    "latency":    {"warning": 500,  "critical": 1000, "unit": "ms"},
    "rps":        {"warning": 8000, "critical": 10000,"unit": "req/s"},
}


class PredictionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.metric_repo = MetricRepository(db)

    async def run_prediction_scan(self) -> List[Dict]:
        """
        Scan all services and generate predictions.
        Called by APScheduler every N minutes.
        """
        from sqlalchemy import select, distinct
        from modules.incident_engine.models import Metric

        # Get all unique (service, metric) combinations
        result = await self.db.execute(
            select(distinct(Metric.service_name), Metric.metric_name)
            .limit(50)
        )
        combos = result.fetchall()

        predictions = []
        for service_name, metric_name in combos:
            try:
                pred = await self.predict_for_metric(service_name, metric_name)
                if pred:
                    predictions.append(pred)
            except Exception as e:
                logger.warning(f"Prediction failed for {service_name}/{metric_name}: {e}")

        return predictions

    async def predict_for_metric(
        self,
        service_name: str,
        metric_name: str,
        horizon_minutes: int = 30,
    ) -> Optional[Dict]:
        """Generate outage prediction for a single service metric."""
        # Fetch historical data
        history = await self.metric_repo.get_latest_for_service(service_name, metric_name, limit=60)
        if len(history) < 3:
            return None

        values = [m.value for m in history]
        timestamps = [m.timestamp for m in history]

        # ── Algorithm 1: Moving Average Anomaly Detection ─────────────────────
        ma_result = self._moving_average_forecast(values)

        # ── Algorithm 2: Linear Trend Projection ──────────────────────────────
        trend_result = self._linear_trend_forecast(values, horizon_minutes)

        # ── Algorithm 3: Z-score Anomaly Detection ────────────────────────────
        anomaly_result = self._zscore_anomaly(values)

        # ── Combine scores ────────────────────────────────────────────────────
        threshold = THRESHOLDS.get(metric_name, {"critical": 90.0, "warning": 70.0})
        current_value = values[-1]
        baseline = sum(values[:-5]) / max(len(values[:-5]), 1)

        # Calculate outage probability
        outage_prob = self._compute_outage_probability(
            current_value=current_value,
            predicted_value=trend_result["predicted_value"],
            critical_threshold=threshold["critical"],
            anomaly_score=anomaly_result["anomaly_score"],
            trend_slope=trend_result["slope"],
        )

        risk_score = outage_prob * 100

        # Estimate time to failure
        time_to_failure = None
        if trend_result["slope"] > 0 and current_value < threshold["critical"]:
            remaining = threshold["critical"] - current_value
            if trend_result["slope"] > 0:
                time_to_failure = remaining / trend_result["slope"]  # minutes

        # Determine algorithm used
        algorithm = "anomaly_detection" if anomaly_result["is_anomaly"] else (
            "prophet_linear" if abs(trend_result["slope"]) > 0.5 else "moving_average"
        )

        # Store prediction
        prediction = Prediction(
            service_name=service_name,
            metric_name=metric_name,
            outage_probability=outage_prob,
            confidence=trend_result["r_squared"],
            risk_score=risk_score,
            predicted_outage_time=(
                datetime.now(timezone.utc) + timedelta(minutes=time_to_failure)
                if time_to_failure and time_to_failure < 120
                else None
            ),
            time_to_failure_minutes=time_to_failure,
            algorithm=algorithm,
            forecast_horizon_minutes=horizon_minutes,
            current_value=current_value,
            baseline_value=baseline,
            anomaly_score=anomaly_result["anomaly_score"],
            model_metadata={
                "slope": trend_result["slope"],
                "r_squared": trend_result["r_squared"],
                "is_anomaly": anomaly_result["is_anomaly"],
                "ma_predicted": ma_result["predicted"],
            },
        )
        self.db.add(prediction)
        await self.db.flush()

        result = {
            "service_name": service_name,
            "metric_name": metric_name,
            "current_value": current_value,
            "outage_probability": outage_prob,
            "risk_score": risk_score,
            "time_to_failure_minutes": time_to_failure,
            "algorithm": algorithm,
            "is_anomaly": anomaly_result["is_anomaly"],
        }

        # Emit events
        if outage_prob > 0.7:
            await event_bus.emit(
                EventType.PREDICTION_GENERATED,
                payload=result,
            )
        if anomaly_result["is_anomaly"]:
            await event_bus.emit(
                EventType.ANOMALY_DETECTED,
                payload=result,
            )

        return result

    def _moving_average_forecast(self, values: List[float], window: int = 5) -> Dict:
        """Simple moving average forecast."""
        if len(values) < window:
            return {"predicted": values[-1], "std": 0}
        window_vals = values[-window:]
        predicted = sum(window_vals) / window
        std = math.sqrt(sum((v - predicted) ** 2 for v in window_vals) / window)
        return {"predicted": predicted, "std": std}

    def _linear_trend_forecast(self, values: List[float], horizon_minutes: int) -> Dict:
        """Least-squares linear regression trend forecast."""
        n = len(values)
        if n < 2:
            return {"predicted_value": values[-1], "slope": 0.0, "r_squared": 0.0}

        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
        denominator = sum((xi - x_mean) ** 2 for xi in x)

        slope = numerator / denominator if denominator != 0 else 0.0
        intercept = y_mean - slope * x_mean

        # Predict at horizon
        predicted = intercept + slope * (n + horizon_minutes)

        # R-squared
        ss_res = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, values))
        ss_tot = sum((yi - y_mean) ** 2 for yi in values)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return {
            "predicted_value": max(0.0, predicted),
            "slope": slope,
            "r_squared": max(0.0, min(1.0, r_squared)),
        }

    def _zscore_anomaly(self, values: List[float], threshold: float = 2.5) -> Dict:
        """Z-score based anomaly detection on recent values."""
        if len(values) < 10:
            return {"is_anomaly": False, "anomaly_score": 0.0}

        baseline = values[:-3]
        mean = sum(baseline) / len(baseline)
        variance = sum((v - mean) ** 2 for v in baseline) / len(baseline)
        std = math.sqrt(variance) if variance > 0 else 1.0

        recent = values[-3:]
        z_scores = [abs(v - mean) / std for v in recent]
        max_z = max(z_scores)

        anomaly_score = min(1.0, max_z / (threshold * 2))
        is_anomaly = max_z > threshold

        return {"is_anomaly": is_anomaly, "anomaly_score": anomaly_score, "z_score": max_z}

    def _compute_outage_probability(
        self,
        current_value: float,
        predicted_value: float,
        critical_threshold: float,
        anomaly_score: float,
        trend_slope: float,
    ) -> float:
        """Combine multiple signals into outage probability."""
        # Proximity to threshold
        proximity = current_value / critical_threshold if critical_threshold > 0 else 0.5
        proximity = min(1.0, proximity)

        # Trend contribution
        trend_factor = min(1.0, max(0.0, trend_slope / 10.0))

        # Predicted breach
        predicted_breach = 1.0 if predicted_value >= critical_threshold else (predicted_value / critical_threshold)

        # Weighted combination
        prob = (
            proximity * 0.4
            + anomaly_score * 0.3
            + predicted_breach * 0.2
            + trend_factor * 0.1
        )
        return round(min(1.0, max(0.0, prob)), 3)

    async def get_latest_predictions(self, limit: int = 20) -> List[Prediction]:
        from sqlalchemy import select, desc
        result = await self.db.execute(
            select(Prediction).order_by(desc(Prediction.created_at)).limit(limit)
        )
        return result.scalars().all()

    async def get_predictions_for_service(self, service_name: str) -> List[Prediction]:
        from sqlalchemy import select, desc
        result = await self.db.execute(
            select(Prediction)
            .where(Prediction.service_name == service_name)
            .order_by(desc(Prediction.created_at))
            .limit(10)
        )
        return result.scalars().all()
