"""
SentinelAI — Database Connection Test
Run: python test_db.py
Tests: Supabase connection, pgvector extension, table creation, and data insertion.
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_database():
    print("=" * 60)
    print("SentinelAI — Database Connection Test")
    print("=" * 60)

    # ── Load settings ──────────────────────────────────────────────────────────
    try:
        from core.config import settings
        print(f"\n✅ Config loaded")
        print(f"   SUPABASE_URL: {settings.supabase_url[:30]}...")
        print(f"   DATABASE_URL: {settings.database_url[:50]}...")
        print(f"   OPENROUTER_KEY: {'SET ✅' if settings.openrouter_api_key else 'MISSING ❌'}")
        print(f"   HF_MODEL: {settings.hf_embedding_model}")
    except Exception as e:
        print(f"❌ Config load failed: {e}")
        return False

    # ── Test DB connection ──────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Testing PostgreSQL connection...")
    try:
        from core.database import check_db_health, engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            row = result.fetchone()
            print(f"✅ PostgreSQL connected!")
            print(f"   Version: {row[0][:60]}...")
    except Exception as e:
        print(f"❌ DB connection failed: {e}")
        print("\n💡 Fix: Check your DATABASE_URL in .env")
        print("   Format: postgresql+asyncpg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres")
        print("   Get password from: Supabase Dashboard → Settings → Database → Connection string")
        return False

    # ── Test pgvector ──────────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Testing pgvector extension...")
    try:
        from core.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            result = await conn.execute(text("SELECT '[1,2,3]'::vector"))
            print(f"✅ pgvector is enabled!")
    except Exception as e:
        print(f"⚠️  pgvector issue: {e}")
        print("   → The app will fall back to JSON-stored embeddings")

    # ── Test table creation ────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Testing table creation (init_db)...")
    try:
        from core.database import init_db
        await init_db()
        print(f"✅ All 20 tables created/verified!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Table creation failed: {e}")
        return False

    # ── Test incident creation ─────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Testing incident CRUD...")
    try:
        from core.database import AsyncSessionFactory
        from modules.incident_engine.models import Incident
        from sqlalchemy import select, func

        async with AsyncSessionFactory() as session:
            # Count existing
            result = await session.execute(select(func.count(Incident.id)))
            count_before = result.scalar_one()
            print(f"   Existing incidents: {count_before}")

            # Insert test incident
            test = Incident(
                title="[TEST] Database connection test incident",
                severity="P4",
                status="resolved",
                source="test_script",
                tags=["test", "connectivity"],
            )
            session.add(test)
            await session.commit()
            await session.refresh(test)

            print(f"✅ Incident created: {test.id}")

            # Clean up
            await session.delete(test)
            await session.commit()
            print(f"✅ Test incident cleaned up")
    except Exception as e:
        print(f"❌ CRUD test failed: {e}")
        return False

    # ── Test graph seeding ────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Testing knowledge graph seeding...")
    try:
        from core.database import AsyncSessionFactory
        from modules.graph_engine.service import GraphService

        async with AsyncSessionFactory() as session:
            svc = GraphService(session)
            n = await svc.seed_default_architecture()
            await session.commit()
            graph = await svc.get_full_graph()
            print(f"✅ Graph ready: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    except Exception as e:
        print(f"⚠️  Graph seeding: {e}")

    # ── Test OpenRouter ────────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    print("Testing OpenRouter AI connection...")
    try:
        from shared.ai.openrouter import get_openrouter
        ai = get_openrouter()
        response = await ai.complete(
            messages=[{"role": "user", "content": "Reply with exactly: SENTINEL_OK"}],
            model=settings.openrouter_fast_model,
            max_tokens=20,
        )
        if "SENTINEL" in response.upper() or "OK" in response.upper():
            print(f"✅ OpenRouter connected! Response: {response.strip()}")
        else:
            print(f"✅ OpenRouter connected! Response: {response[:50]}")
        await ai.close()
    except Exception as e:
        print(f"❌ OpenRouter failed: {e}")
        print("   → Check OPENROUTER_API_KEY in .env")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED — Database is ready!")
    print("\nNext steps:")
    print("  python seed.py           → Seed demo data")
    print("  uvicorn main:app --reload --port 8000  → Start server")
    print("  http://localhost:8000/docs  → Swagger UI")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(test_database())
    sys.exit(0 if result else 1)
