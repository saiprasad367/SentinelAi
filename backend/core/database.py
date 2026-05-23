"""
SentinelAI — Database Layer
Async SQLAlchemy engine + Supabase client + pgvector support.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

logger = logging.getLogger("sentinel.database")


class Base(DeclarativeBase):
    """SQLAlchemy declarative base - all models inherit from this."""
    pass


def _make_engine() -> AsyncEngine:
    """Create async SQLAlchemy engine with production settings."""
    db_url = settings.database_url
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill in Supabase credentials."
        )

    return create_async_engine(
        db_url,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={
            "server_settings": {
                "application_name": "sentinel_ai_backend",
            },
            "statement_cache_size": 0,
        },
    )


engine: AsyncEngine = _make_engine()

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency - yields an async DB session."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for use outside FastAPI request context."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Initialize database:
    - Enable pgvector extension
    - Create all tables (dev only - use Alembic in prod)
    """
    async with engine.begin() as conn:
        # Enable pgvector
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        logger.info("PostgreSQL extensions enabled: vector, pg_trgm")

        # Import all models so Base knows about them
        _import_all_models()

        await conn.run_sync(Base.metadata.create_all)
        logger.info("All database tables created/verified")


def _import_all_models() -> None:
    """Import all SQLAlchemy models to register them with Base.metadata."""
    # These imports trigger model registration
    from modules.incident_engine import models as incident_models  # noqa
    from modules.investigation_engine import models as investigation_models  # noqa
    from modules.prediction_engine import models as prediction_models  # noqa
    from modules.memory_engine import models as memory_models  # noqa
    from modules.impact_engine import models as impact_models  # noqa
    from modules.graph_engine import models as graph_models  # noqa
    from modules.chat_engine import models as chat_models  # noqa
    from modules.report_engine import models as report_models  # noqa
    from modules.analytics_engine import models as analytics_models  # noqa
    from modules.replay_engine import models as replay_models  # noqa


async def check_db_health() -> dict:
    """Health check for database connectivity."""
    try:
        async with AsyncSessionFactory() as session:
            result = await session.execute(text("SELECT 1 as health, version() as pg_version"))
            row = result.fetchone()
            return {
                "status": "healthy",
                "pg_version": row.pg_version if row else "unknown",
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
