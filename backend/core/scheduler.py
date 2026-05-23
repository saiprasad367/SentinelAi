"""
SentinelAI — APScheduler Background Job Scheduler
Manages periodic prediction scans, health checks, and analytics aggregation.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings

logger = logging.getLogger("sentinel.scheduler")

scheduler = AsyncIOScheduler(timezone="UTC")


def setup_jobs() -> None:
    """Register all background jobs. Called once at startup."""

    # ── Prediction Engine: periodic metric scan ───────────────────────────────
    scheduler.add_job(
        _run_prediction_scan,
        trigger=IntervalTrigger(minutes=settings.prediction_scan_interval_minutes),
        id="prediction_scan",
        name="Outage Prediction Scan",
        replace_existing=True,
        max_instances=1,
    )

    # ── Service Health Monitor ─────────────────────────────────────────────────
    scheduler.add_job(
        _run_health_monitor,
        trigger=IntervalTrigger(seconds=settings.health_check_interval_seconds),
        id="health_monitor",
        name="Service Health Monitor",
        replace_existing=True,
        max_instances=1,
    )

    # ── Analytics Aggregator ──────────────────────────────────────────────────
    scheduler.add_job(
        _run_analytics_aggregation,
        trigger=IntervalTrigger(minutes=settings.analytics_aggregation_interval_minutes),
        id="analytics_aggregator",
        name="Analytics Aggregation",
        replace_existing=True,
        max_instances=1,
    )

    logger.info(f"Registered {len(scheduler.get_jobs())} background jobs")


async def _run_prediction_scan() -> None:
    """Periodic outage prediction scan across all services."""
    try:
        from modules.prediction_engine.service import PredictionService
        from core.database import get_db_context
        async with get_db_context() as db:
            service = PredictionService(db)
            await service.run_prediction_scan()
    except Exception as e:
        logger.error(f"Prediction scan failed: {e}")


async def _run_health_monitor() -> None:
    """Monitor service health and emit events on changes."""
    try:
        from modules.graph_engine.service import GraphService
        from core.database import get_db_context
        async with get_db_context() as db:
            service = GraphService(db)
            await service.check_and_emit_health_changes()
    except Exception as e:
        logger.error(f"Health monitor failed: {e}")


async def _run_analytics_aggregation() -> None:
    """Aggregate analytics snapshots (MTTR, MTBF, trends)."""
    try:
        from modules.analytics_engine.service import AnalyticsService
        from core.database import get_db_context
        async with get_db_context() as db:
            service = AnalyticsService(db)
            await service.aggregate_snapshot()
    except Exception as e:
        logger.error(f"Analytics aggregation failed: {e}")
