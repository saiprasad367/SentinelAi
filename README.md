# SentinelAI — The Autonomous SRE

SentinelAI is an AI-powered reliability engineering platform that detects incidents, runs live diagnostic investigations, traces blast-radius cascades, recalls historical resolutions semantically, and automatically generates board-ready post-mortem PDF reports.

This repository is structured as a modular SRE workspace:
* **`backend/`**: FastAPI modular monolith simulating an agentic reliability engineer, connected to a Supabase database (with `pgvector` enabled) and OpenRouter AI.
* **`sentinelai-insight/`**: React TanStack Start frontend dashboard designed with premium dark/glassmorphic aesthetics and real-time state synchronization.

---

## 🚀 Getting Started

Ensure you have **Python 3.12+** and **Node.js 18+** installed.

### 1. Setup the Database & AI Credentials
First, verify that your credentials are set up. Create/verify the `.env` file in the `backend/` directory:

```env
# Supabase Database (pgvector enabled)
SUPABASE_URL=https://your-supabase-url.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:6543/postgres
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:[PASSWORD]@db.[REF].supabase.co:6543/postgres

# OpenRouter AI Keys
OPENROUTER_API_KEY=sk-or-v1-your-key
OPENROUTER_DEFAULT_MODEL=anthropic/claude-3-haiku
OPENROUTER_FAST_MODEL=openai/gpt-4o-mini
OPENROUTER_STRONG_MODEL=anthropic/claude-3-5-sonnet
```

---

### 2. Start the Backend Server

```bash
cd backend

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Seed default graph structure, incident logs, and metric baselines
python seed.py

# 3. Start the FastAPI development server
uvicorn main:app --reload --port 8000
```
Verify the API is running by visiting:
* Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
* Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

### 3. Start the Frontend Dashboard

```bash
cd sentinelai-insight

# Start the React / Vite development server
npm run dev
```

Open your browser at [http://localhost:3000](http://localhost:3000) (or the port output by the dev server).

---

## 🛡️ Step-by-Step E2E Testing Script

Follow these steps to experience the complete SRE workflow and verify that the backend-frontend integration is functioning perfectly:

### Step 1: Trigger an Outage
* Scroll to the **AI Investigation Center** section at the top of the dashboard.
* Click the **"Trigger Demo Outage (Payment API)"** button. 
* This makes a POST request to `/api/v1/incidents` to create a live incident in the database, automatically triggering the AI agent diagnostics.

### Step 2: Watch AI Stream its Thoughts Live
* As soon as the outage is triggered, look at the **Agent Diagnostics Terminal** on the right side.
* You will see the AI SRE agent stream its live diagnostic steps and reasoning steps using Server-Sent Events (SSE).
* Watch the **AI Confidence** percentage update as it compiles clues from logs, checks metric baselines, and traces routes.

### Step 3: Run Blast-Radius BFS Cascades
* Scroll down to the **Infrastructure Digital Twin** knowledge graph.
* The graph automatically loads monitored services and health status from the backend database.
* Select the **Payment API** (or any service) and click **"Simulate Failure"**.
* Watch the live BFS traversal cascading down through direct and indirect dependencies, highlighting the blast path in red/orange.

### Step 4: Inspect Financial & Urgency Impacts
* Look at the **Business Impact Story** timeline.
* The component dynamically translates the failure into financial scale, calculating the estimated loss per minute, urgency score, and the exact percentage of checkout traffic blocked by the incident.

### Step 5: Semantic Memory Recall
* Go to the **AI Memory Brain** section.
* Type a search query in the search bar (e.g. `"database pool exhaustion"` or `"oom"`) and hit Enter.
* The backend runs a `pgvector` Cosine Similarity search over historical incidents, returning the most matching entries with their AI-recalled root causes and resolutions.

### Step 6: Apply Mitigation Playbook
* In the **Resolution Simulator** section, review the AI's proposed remediation checklist.
* Click the **"Apply suggested fix"** button.
* This executes a POST request to `/api/v1/incidents/{id}/resolve` on the backend, updating the status in Supabase.
* Watch the system health gauge animate and climb back up to **98% (Healthy)** in real-time.

### Step 7: Rewind and Replay Telemetry
* Scroll to **Incident Replay**.
* Drag the slider back and forth to rewind the outage timeline frame-by-frame. 
* You will see real-time metrics (CPU Load, Memory Usage, Error Rate, and Latency response time) adjust dynamically at each timestamp.

### Step 8: Generate dynamic Board-Ready PDF Post-Mortem
* Scroll to the **AI Executive Report** section at the bottom.
* Select the incident you just resolved from the dropdown list.
* Under the **Distribution Hub** list, click **"Download"** next to **Export PDF Report**.
* A board-ready PDF summarizing the incident description, AI narrative, MTTR metrics, and resolution status will be generated dynamically on the fly and downloaded to your machine!
