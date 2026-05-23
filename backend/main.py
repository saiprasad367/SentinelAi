"""
SentinelAI — Main FastAPI Application
Modular Monolith: all engines wired together as one app.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.database import check_db_health, init_db
from core.events import EventType, event_bus
from core.scheduler import scheduler, setup_jobs

# ── Structured Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("sentinel.main")


# ── Event Listeners ───────────────────────────────────────────────────────────

async def on_incident_detected(event) -> None:
    """When incident detected → auto-trigger investigation + impact calc."""
    incident_id = event.payload.get("incident_id")
    if not incident_id:
        return
    from uuid import UUID
    from core.database import get_db_context

    # Launch investigation
    try:
        async with get_db_context() as db:
            from modules.investigation_engine.service import InvestigationService
            svc = InvestigationService(db)
            await svc.start_investigation(UUID(incident_id))
            logger.info(f"Auto-launched investigation for incident {incident_id}")
    except Exception as e:
        logger.error(f"Auto-investigation failed for {incident_id}: {e}")

    # Calculate impact
    try:
        async with get_db_context() as db:
            from modules.impact_engine.service import ImpactService
            svc = ImpactService(db)
            await svc.calculate_impact(UUID(incident_id))
            logger.info(f"Auto-calculated impact for incident {incident_id}")
    except Exception as e:
        logger.error(f"Auto-impact failed for {incident_id}: {e}")


async def on_incident_resolved(event) -> None:
    """When incident resolved → store in memory bank + generate report."""
    incident_id = event.payload.get("incident_id")
    if not incident_id:
        return
    from uuid import UUID
    from core.database import get_db_context

    # Store in memory
    try:
        async with get_db_context() as db:
            from modules.memory_engine.service import MemoryService
            svc = MemoryService(db)
            await svc.store_incident_memory(UUID(incident_id))
    except Exception as e:
        logger.error(f"Memory storage failed for {incident_id}: {e}")

    # Seed replay events
    try:
        async with get_db_context() as db:
            from modules.replay_engine.service import ReplayService
            svc = ReplayService(db)
            await svc.seed_replay_events(UUID(incident_id))
    except Exception as e:
        logger.debug(f"Replay seed failed: {e}")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version} [{settings.app_env}]")

    # Initialize database and pgvector
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")
        logger.warning("Continuing without database connection (set DATABASE_URL in .env)")

    # Register event listeners
    event_bus.subscribe(EventType.INCIDENT_DETECTED, on_incident_detected)
    event_bus.subscribe(EventType.INCIDENT_RESOLVED, on_incident_resolved)

    # Register WebSocket broadcaster (subscribes to ALL events)
    from modules.notification_engine.controller import handle_event_broadcast
    event_bus.subscribe_all(handle_event_broadcast)

    # Start event bus
    await event_bus.start()
    logger.info("✅ Event bus started")

    # Seed default architecture graph
    try:
        from core.database import get_db_context
        from modules.graph_engine.service import GraphService
        async with get_db_context() as db:
            svc = GraphService(db)
            count = await svc.seed_default_architecture()
            if count > 0:
                logger.info(f"✅ Seeded {count} architecture nodes")
    except Exception as e:
        logger.debug(f"Graph seed skipped: {e}")

    # Start scheduler
    setup_jobs()
    scheduler.start()
    logger.info(f"✅ Scheduler started with {len(scheduler.get_jobs())} jobs")

    logger.info(f"✅ {settings.app_name} is ready! http://{settings.host}:{settings.port}")
    logger.info(f"   📖 Docs: http://{settings.host}:{settings.port}/docs")

    yield

    # Shutdown
    logger.info("Shutting down SentinelAI...")
    scheduler.shutdown(wait=False)
    await event_bus.stop()
    from shared.ai.openrouter import close_openrouter
    await close_openrouter()
    logger.info("Goodbye! 👋")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="SentinelAI API",
    description="""
## SentinelAI — The Autonomous Reliability Engineer

AI-powered incident detection, root cause analysis, outage prediction,
business impact estimation, and automated post-mortem generation.

### Features
- 🔍 **Incident Detection** — Upload logs, ingest JSON events, auto-detect failures
- 🧠 **AI Investigation** — 6-step root cause workflow with SSE streaming
- 📡 **Knowledge Graph** — BFS blast radius across service dependencies  
- 🔮 **Prediction Engine** — Time-series forecasting with anomaly detection
- 💾 **Memory Bank** — pgvector semantic search over resolved incidents
- 💼 **Business Impact** — Revenue loss estimation and urgency scoring
- 💬 **AI Chat** — RAG-powered SRE assistant with streaming
- 📄 **PDF Reports** — Executive post-mortem generation
- 🔴 **Realtime** — WebSocket + SSE event streams
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Timing Middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
    return response


# ── Health Check ─────────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """System health check endpoint."""
    db_health = await check_db_health()
    return {
        "status": "healthy" if db_health["status"] == "healthy" else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_health,
        "event_bus": "running",
        "scheduler_jobs": len(scheduler.get_jobs()),
    }


# ── Include All Module Routers ────────────────────────────────────────────────
from modules.incident_engine.controller import router as incidents_router
from modules.investigation_engine.controller import router as investigations_router
from modules.graph_engine.controller import router as graph_router
from modules.prediction_engine.controller import router as predictions_router
from modules.memory_engine.controller import router as memory_router
from modules.impact_engine.controller import router as impact_router
from modules.chat_engine.controller import router as chat_router
from modules.report_engine.controller import router as reports_router
from modules.analytics_engine.controller import router as analytics_router
from modules.replay_engine.controller import router as replay_router
from modules.notification_engine.controller import router as realtime_router

API_PREFIX = "/api/v1"

app.include_router(incidents_router,     prefix=API_PREFIX)
app.include_router(investigations_router, prefix=API_PREFIX)
app.include_router(graph_router,          prefix=API_PREFIX)
app.include_router(predictions_router,    prefix=API_PREFIX)
app.include_router(memory_router,         prefix=API_PREFIX)
app.include_router(impact_router,         prefix=API_PREFIX)
app.include_router(chat_router,           prefix=API_PREFIX)
app.include_router(reports_router,        prefix=API_PREFIX)
app.include_router(analytics_router,      prefix=API_PREFIX)
app.include_router(replay_router,         prefix=API_PREFIX)
app.include_router(realtime_router,       prefix=API_PREFIX)


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "SentinelAI API",
        "tagline": "The Autonomous Reliability Engineer",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/health",
        "websocket": "/api/v1/realtime/ws",
    }


# ── Exception Handler ─────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
