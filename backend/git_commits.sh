#!/bin/bash
# SentinelAI — Git Commit Script
# Run from the root of the repository: c:\Users\saipr\Music\SentinelAI
# This script makes feature-wise commits to https://github.com/saiprasad367/SentinelAi.git

set -e

echo "🚀 SentinelAI — Feature-wise Git Commits"
echo "=========================================="

# Configure git if needed
git config user.email "sentinel@ai.dev" 2>/dev/null || true
git config user.name "SentinelAI" 2>/dev/null || true

# Make sure we have the remote set
git remote add origin https://github.com/saiprasad367/SentinelAi.git 2>/dev/null || true

# ── Commit 1: Project Scaffold ────────────────────────────────────────────────
echo ""
echo "📦 Commit 1: Project scaffold, core config, database models"
git add backend/requirements.txt
git add backend/.env.example
git add backend/.gitignore
git add backend/core/
git add backend/shared/
git add backend/modules/__init__.py
git add backend/modules/shared_models.py
git commit -m "feat: project scaffold - core config, database, event bus, AI clients

- FastAPI modular monolith architecture
- Async SQLAlchemy with pgvector support
- Internal pub/sub event bus (zero external dependencies)
- OpenRouter AI client with streaming support
- HuggingFace BGE embeddings client
- APScheduler background job scheduler
- All 20 database table schemas defined
- pydantic-settings configuration (zero hardcoded values)"

# ── Commit 2: Incident Detection Engine ──────────────────────────────────────
echo ""
echo "🚨 Commit 2: Incident Detection Engine"
git add backend/modules/incident_engine/
git add backend/main.py
git commit -m "feat: incident detection engine with log/JSON/CSV parsing

- Multi-format log parser (plain text, JSON, JSONL, CSV)
- Severity classification (P1-P4) from error patterns
- Regex-based error/service extraction
- File upload endpoint (up to 50MB)
- Metric ingestion API with batch support
- Auto-incident creation from log analysis
- Full CRUD API: GET/POST /api/v1/incidents
- Event emission on incident creation (triggers investigation)"

# ── Commit 3: Investigation Engine + SSE ─────────────────────────────────────
echo ""
echo "🧠 Commit 3: Root Cause Investigation Engine + AI Thinking SSE Stream"
git add backend/modules/investigation_engine/
git commit -m "feat: AI root cause investigation engine with SSE streaming

- 6-step investigation workflow (logs → metrics → graph → memory → deploy → synthesis)
- Real OpenRouter AI integration for root cause synthesis
- Server-Sent Events stream at /api/v1/investigations/{id}/stream
- Background async task (non-blocking investigation)
- Per-step DB updates with confidence scores
- Auto-triggered on incident creation via event bus
- AI narrative generation with evidence citations"

# ── Commit 4: Knowledge Graph + Blast Radius ─────────────────────────────────
echo ""
echo "🗺️  Commit 4: Infrastructure Knowledge Graph + BFS Blast Radius"
git add backend/modules/graph_engine/
git commit -m "feat: infrastructure knowledge graph with BFS blast radius engine

- Default 12-node architecture pre-seeded (payment, auth, gateway, DB, cache...)
- 15 dependency edges with relationship types
- BFS traversal for blast radius computation
- Criticality scoring (0-100) based on service importance
- Direct vs indirect impact classification
- Health status management with event emission
- REST API: GET /api/v1/graph, /blast-radius/{node}"

# ── Commit 5: Prediction Engine ───────────────────────────────────────────────
echo ""
echo "🔮 Commit 5: Outage Prediction Engine"
git add backend/modules/prediction_engine/
git commit -m "feat: outage prediction engine with multi-algorithm forecasting

- Moving average anomaly detection
- Least-squares linear regression trend projection
- Z-score based anomaly detection (2.5σ threshold)
- Combined outage probability scoring
- Time-to-failure estimation in minutes
- APScheduler periodic scan every 5 minutes
- Per-metric and per-service predictions
- REST API: GET /api/v1/predictions/latest, POST /scan"

# ── Commit 6: Memory Engine (pgvector) ───────────────────────────────────────
echo ""
echo "💾 Commit 6: AI Memory Engine with pgvector Semantic Search"
git add backend/modules/memory_engine/
git commit -m "feat: AI memory engine with pgvector semantic search

- BAAI/bge-small-en-v1.5 embeddings via HuggingFace
- pgvector cosine similarity search in PostgreSQL
- Python cosine similarity fallback (robust deployment)
- Auto-stores resolved incidents as searchable memories
- Triggered by INCIDENT_RESOLVED event
- Similarity search with configurable threshold
- REST API: POST /api/v1/memory/search, /store/{id}"

# ── Commit 7: Business Impact Engine ─────────────────────────────────────────
echo ""
echo "💼 Commit 7: Business Impact Engine"
git add backend/modules/impact_engine/
git commit -m "feat: business impact engine with AI recommendation generation

- Severity-based user impact calculation (P1=100% → P4=2%)
- Revenue loss estimation ($1500/min * severity multiplier)
- Blast radius integration from graph engine
- Business criticality scoring (0-100)
- AI-generated remediation recommendations (OpenRouter)
- Auto-triggered on incident creation
- REST API: POST/GET /api/v1/impact/{incident_id}"

# ── Commit 8: AI Chat Engine ──────────────────────────────────────────────────
echo ""
echo "💬 Commit 8: AI Chat Engine with RAG"
git add backend/modules/chat_engine/
git commit -m "feat: RAG-powered AI chat engine with streaming responses

- Full RAG pipeline: incidents + memory + predictions as context
- OpenRouter streaming via SSE
- Session management with conversation history
- Context injection from all system sources
- Citation tracking for AI responses
- SSE stream: GET /api/v1/chat/sessions/{id}/stream
- Non-streaming: POST /api/v1/chat/sessions/{id}/messages"

# ── Commit 9: PDF Report Engine ───────────────────────────────────────────────
echo ""
echo "📄 Commit 9: PDF Executive Report Engine"
git add backend/modules/report_engine/
git commit -m "feat: PDF post-mortem report engine with ReportLab

- Professional PDF layout with SentinelAI branding
- Sections: Executive Summary, Overview, Root Cause, Impact, Recommendations
- AI-generated executive summary via OpenRouter
- Impact and recommendation data aggregation
- File download endpoint (application/pdf)
- REST API: POST /api/v1/reports/generate, GET /{id}/download"

# ── Commit 10: Analytics + Replay ─────────────────────────────────────────────
echo ""
echo "📊 Commit 10: Analytics Engine + Incident Replay Engine"
git add backend/modules/analytics_engine/
git add backend/modules/replay_engine/
git commit -m "feat: analytics engine (MTTR/MTBF) + incident replay timeline

- Analytics: MTTR, MTBF, 7-day trends, by-severity counts, prediction accuracy
- APScheduler aggregation every 15 minutes
- Replay: 11-event synthetic timeline (healthy → failure → recovery)
- Metric snapshots at each replay event
- Auto-seeded on incident creation
- REST API: /api/v1/analytics/summary, /api/v1/replay/{id}/events"

# ── Commit 11: Realtime WebSocket Hub ────────────────────────────────────────
echo ""
echo "🔴 Commit 11: WebSocket Realtime Hub + Event Broadcasting"
git add backend/modules/notification_engine/
git commit -m "feat: WebSocket realtime hub with full event broadcasting

- ConnectionManager for WebSocket lifecycle
- All event bus events broadcast to connected clients
- SSE fallback at /api/v1/realtime/events
- Keepalive ping/pong every 30s
- Connection count tracking
- WS endpoint: /api/v1/realtime/ws"

# ── Commit 12: Seeder + README ────────────────────────────────────────────────
echo ""
echo "🌱 Commit 12: Database Seeder + README"
git add backend/seed.py
git add backend/README.md
git commit -m "feat: database seeder with realistic demo data + full README

Seeder populates:
- 5 realistic incidents (P1-P3) with root causes and AI analysis
- 128+ metric data points with realistic degradation curves
- 12-node architecture graph (pre-wired)
- Incident replay timelines
- Incident memory embeddings for semantic search
- Analytics snapshot

README: setup instructions, API reference, architecture diagram"

# ── Push ──────────────────────────────────────────────────────────────────────
echo ""
echo "🚀 Pushing all commits to GitHub..."
git push -u origin main

echo ""
echo "✅ All 12 feature commits pushed to https://github.com/saiprasad367/SentinelAi.git"
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and add your credentials"
echo "  2. pip install -r requirements.txt"
echo "  3. python seed.py"
echo "  4. uvicorn main:app --reload --port 8000"
