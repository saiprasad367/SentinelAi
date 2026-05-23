# SentinelAI Backend

> **The Autonomous Reliability Engineer** — AI-powered incident detection, root cause analysis, outage prediction, and automated post-mortem generation.

## 🏗️ Architecture

Modular Monolith (looks like microservices, runs as one FastAPI app):

```
backend/
├── main.py                    # FastAPI entry point
├── core/                      # Shared infrastructure
│   ├── config.py              # All settings (env vars)
│   ├── database.py            # SQLAlchemy async + pgvector
│   ├── events.py              # Internal pub/sub event bus
│   └── scheduler.py           # APScheduler background jobs
├── modules/
│   ├── incident_engine/       # Log parsing, incident detection
│   ├── investigation_engine/  # AI root cause + SSE stream
│   ├── graph_engine/          # Knowledge graph + BFS blast radius
│   ├── prediction_engine/     # Time-series forecasting + anomaly
│   ├── memory_engine/         # pgvector semantic search
│   ├── impact_engine/         # Business impact scoring
│   ├── chat_engine/           # RAG AI chat (streaming)
│   ├── report_engine/         # PDF post-mortem generation
│   ├── analytics_engine/      # MTTR, MTBF, trends
│   ├── replay_engine/         # Incident timeline replay
│   └── notification_engine/   # WebSocket + SSE hub
└── shared/ai/                 # OpenRouter + HuggingFace embeddings
```

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.12+
- Supabase project with pgvector enabled
- OpenRouter API key

### 2. Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your Supabase + OpenRouter credentials

# Seed the database with demo data
python seed.py

# Start the server
uvicorn main:app --reload --port 8000
```

### 3. Verify

```
http://localhost:8000/          → API info
http://localhost:8000/docs      → Swagger UI
http://localhost:8000/api/v1/health  → Health check
```

## 🔑 Required Environment Variables

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
DATABASE_URL=postgresql+asyncpg://postgres:password@db.xxx.supabase.co:5432/postgres
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:password@db.xxx.supabase.co:5432/postgres

# OpenRouter AI
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_DEFAULT_MODEL=anthropic/claude-3-haiku
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | System health |
| POST | `/api/v1/incidents` | Create incident |
| POST | `/api/v1/incidents/upload` | Upload log file |
| GET | `/api/v1/incidents` | List incidents |
| POST | `/api/v1/investigations` | Start AI investigation |
| GET | `/api/v1/investigations/{id}/stream` | SSE: AI thinking stream |
| GET | `/api/v1/graph` | Knowledge graph |
| GET | `/api/v1/graph/blast-radius/{node}` | BFS blast radius |
| GET | `/api/v1/predictions/latest` | Latest predictions |
| POST | `/api/v1/memory/search` | Semantic search |
| POST | `/api/v1/impact/{id}` | Calculate business impact |
| POST | `/api/v1/chat/sessions` | Create chat session |
| GET | `/api/v1/chat/sessions/{id}/stream` | SSE: AI chat stream |
| POST | `/api/v1/reports/generate` | Generate PDF report |
| GET | `/api/v1/analytics/summary` | MTTR, MTBF, trends |
| WS | `/api/v1/realtime/ws` | WebSocket event stream |

## 🧠 AI Workflows

### Incident → Auto-Investigation → Auto-Impact

1. Incident created (API or log upload)
2. Event bus emits `INCIDENT_DETECTED`
3. Investigation engine auto-starts 6-step workflow
4. Impact engine calculates blast radius + revenue loss
5. SSE stream delivers step updates to frontend
6. Root cause stored, recommendations generated

### Resolved → Memory → Searchable

1. Incident resolved
2. Event bus emits `INCIDENT_RESOLVED`
3. Memory engine generates BGE embeddings
4. Stored in pgvector for semantic search
5. Future similar incidents matched in O(log n) time

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115 |
| Python | 3.12 |
| Database | Supabase PostgreSQL |
| ORM | SQLAlchemy 2.0 (async) |
| Vector Store | pgvector |
| AI | OpenRouter (configurable models) |
| Embeddings | BAAI/bge-small-en-v1.5 |
| Scheduler | APScheduler |
| PDF | ReportLab |
| Realtime | WebSocket + SSE |
