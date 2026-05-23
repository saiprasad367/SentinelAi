"""
SentinelAI — Database Seeder
Populates the database with realistic demo data for hackathon demonstrations.
Run: python seed.py
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

logger = logging.getLogger("sentinel.seed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


SAMPLE_INCIDENTS = [
    {
        "title": "Payment API connection pool exhausted",
        "description": "Database connection pool reached maximum capacity. New connection requests timing out after 30s. Affecting 100% of payment transactions.",
        "severity": "P1",
        "affected_service": "payment-api",
        "status": "resolved",
        "root_cause": "Connection pool misconfiguration after recent deployment. Max connections set to 10 instead of 100. Caused by environment variable override in Kubernetes ConfigMap.",
        "root_cause_confidence": 0.94,
        "tags": ["database", "connection-pool", "deployment"],
    },
    {
        "title": "Auth service JWT validation failures",
        "description": "JWT token validation failing for 23% of requests. Users being logged out unexpectedly. Started after certificate rotation.",
        "severity": "P2",
        "affected_service": "auth-service",
        "status": "resolved",
        "root_cause": "Certificate rotation completed but old JWTs still in circulation with 1h TTL. New public key not yet propagated to all auth replicas.",
        "root_cause_confidence": 0.89,
        "tags": ["auth", "jwt", "certificate-rotation"],
    },
    {
        "title": "Redis cache eviction causing DB overload",
        "description": "Redis memory limit reached. LRU eviction causing cache miss storm. PostgreSQL receiving 10x normal query load.",
        "severity": "P2",
        "affected_service": "redis-cache",
        "status": "resolved",
        "root_cause": "Redis maxmemory set to 2GB but actual data growth exceeded this due to session size increase after feature flag rollout.",
        "root_cause_confidence": 0.91,
        "tags": ["redis", "cache", "database-overload"],
    },
    {
        "title": "Order service timeout cascade",
        "description": "Order service P99 latency exceeding 5000ms. Circuit breaker tripping. Downstream notification service not receiving order events.",
        "severity": "P1",
        "affected_service": "order-service",
        "status": "investigating",
        "root_cause": None,
        "root_cause_confidence": None,
        "tags": ["timeout", "circuit-breaker", "cascade"],
    },
    {
        "title": "Frontend CDN edge cache invalidation failure",
        "description": "CSS/JS assets serving stale content after v2.4.1 deploy. Cache purge API returned 200 but old assets still cached at edge nodes.",
        "severity": "P3",
        "affected_service": "frontend",
        "status": "resolved",
        "root_cause": "CDN cache invalidation API rate limit exceeded. Only 40% of edge nodes received purge command. Manual node-by-node purge required.",
        "root_cause_confidence": 0.87,
        "tags": ["cdn", "cache", "frontend", "deployment"],
    },
]

SAMPLE_METRICS = [
    ("payment-api", "cpu", [22, 25, 28, 35, 42, 55, 68, 75, 82, 88, 91, 87, 72, 55, 35, 28]),
    ("payment-api", "error_rate", [0.1, 0.1, 0.2, 0.5, 1.2, 3.4, 8.2, 12.5, 18.3, 22.1, 15.2, 8.4, 3.1, 0.8, 0.2, 0.1]),
    ("payment-api", "latency", [85, 88, 92, 105, 145, 280, 540, 890, 1200, 1450, 980, 620, 340, 180, 110, 92]),
    ("auth-service", "cpu", [15, 16, 17, 18, 22, 25, 28, 30, 28, 25, 22, 20, 18, 17, 16, 15]),
    ("auth-service", "error_rate", [0.0, 0.0, 0.1, 0.2, 0.8, 2.1, 4.5, 8.2, 15.3, 12.1, 7.4, 3.2, 1.1, 0.3, 0.1, 0.0]),
    ("redis-cache", "memory", [45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98, 92, 78, 65, 55]),
    ("order-service", "latency", [120, 125, 130, 145, 180, 250, 380, 650, 1100, 1800, 2500, 3200, 4100, 4800, 4900, 4950]),
    ("postgres-main", "cpu", [30, 32, 35, 40, 48, 58, 72, 85, 91, 94, 88, 75, 60, 45, 38, 32]),
]


async def seed():
    """Main seeder function."""
    from core.database import init_db, get_db_context
    from modules.incident_engine.service import IncidentService
    from modules.incident_engine.repository import MetricRepository
    from modules.graph_engine.service import GraphService
    from modules.replay_engine.service import ReplayService

    logger.info("🌱 Starting SentinelAI database seeder...")

    # Initialize DB
    await init_db()

    async with get_db_context() as db:
        # ── Seed Architecture Graph ────────────────────────────────────────────
        logger.info("Seeding knowledge graph...")
        graph_svc = GraphService(db)
        await graph_svc.seed_default_architecture()
        await db.commit()
        logger.info("✅ Architecture graph seeded")

        # ── Seed Incidents ─────────────────────────────────────────────────────
        logger.info("Seeding incidents...")
        svc = IncidentService(db)
        seeded_incident_ids = []

        now = datetime.now(timezone.utc)
        for i, inc_data in enumerate(SAMPLE_INCIDENTS):
            # Don't emit events during seeding (bypass service layer)
            from modules.incident_engine.models import Incident, IncidentStatus, Severity
            from modules.incident_engine.repository import IncidentRepository
            inc_repo = IncidentRepository(db)

            detected_at = now - timedelta(hours=random.randint(1, 72))
            resolved_at = detected_at + timedelta(minutes=random.randint(15, 120)) if inc_data["status"] == "resolved" else None

            incident = await inc_repo.create(
                title=inc_data["title"],
                description=inc_data["description"],
                severity=inc_data["severity"],
                status=inc_data["status"],
                affected_service=inc_data["affected_service"],
                affected_services=[inc_data["affected_service"]],
                source="seed",
                root_cause=inc_data.get("root_cause"),
                root_cause_confidence=inc_data.get("root_cause_confidence"),
                tags=inc_data.get("tags", []),
                detected_at=detected_at,
                resolved_at=resolved_at,
            )
            seeded_incident_ids.append(incident.id)
            logger.info(f"  ✅ Incident: [{inc_data['severity']}] {inc_data['title'][:50]}")

        await db.commit()

        # ── Seed Metrics ───────────────────────────────────────────────────────
        logger.info("Seeding metrics time series...")
        metric_repo = MetricRepository(db)
        base_time = now - timedelta(hours=4)

        metric_data = []
        for service, metric_name, values in SAMPLE_METRICS:
            for i, val in enumerate(values):
                metric_data.append({
                    "service_name": service,
                    "metric_name": metric_name,
                    "value": float(val),
                    "unit": "percent" if metric_name in ("cpu", "memory", "error_rate") else "ms",
                    "timestamp": base_time + timedelta(minutes=i * 15),
                    "labels": {},
                })

        await metric_repo.bulk_create(metric_data)
        await db.commit()
        logger.info(f"  ✅ {len(metric_data)} metric data points seeded")

        # ── Seed Replay Events ─────────────────────────────────────────────────
        logger.info("Seeding replay events...")
        replay_svc = ReplayService(db)
        for inc_id in seeded_incident_ids[:3]:
            try:
                await replay_svc.seed_replay_events(inc_id)
            except Exception as e:
                logger.warning(f"Replay seed failed: {e}")
        await db.commit()
        logger.info("  ✅ Replay events seeded")

        # ── Seed Memories for resolved incidents ───────────────────────────────
        logger.info("Seeding incident memories...")
        from modules.memory_engine.service import MemoryService
        mem_svc = MemoryService(db)
        for i, inc_id in enumerate(seeded_incident_ids):
            inc_data = SAMPLE_INCIDENTS[i]
            if inc_data.get("root_cause"):
                try:
                    await mem_svc.store_incident_memory(inc_id)
                except Exception as e:
                    logger.warning(f"Memory seed failed: {e}")
        await db.commit()
        logger.info("  ✅ Incident memories stored")

        # ── Seed Analytics Snapshot ────────────────────────────────────────────
        logger.info("Generating analytics snapshot...")
        from modules.analytics_engine.service import AnalyticsService
        analytics_svc = AnalyticsService(db)
        try:
            await analytics_svc.aggregate_snapshot()
            await db.commit()
            logger.info("  ✅ Analytics snapshot created")
        except Exception as e:
            logger.warning(f"Analytics snapshot failed: {e}")

    logger.info("")
    logger.info("🎉 Seeding complete!")
    logger.info(f"   📊 {len(SAMPLE_INCIDENTS)} incidents")
    logger.info(f"   📈 {len(metric_data)} metric data points")
    logger.info(f"   🗺️  12 architecture nodes")
    logger.info(f"   🧠 Incident memories stored")
    logger.info("")
    logger.info("Run: uvicorn main:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(seed())
