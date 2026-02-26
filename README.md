# ⚡ ATHENA

**Autonomous Multi-Agent Market Intelligence & Strategy Platform**

> Built for the **Complete AI Hackathon** · Powered by [Deploy.AI](https://deploy.ai)

ATHENA orchestrates a four-stage AI pipeline that transforms a company name, product, or market into a full competitive intelligence package — SWOT analysis, Go-to-Market plan, Markdown report, and pitch deck outline — all in a single click.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ATHENA Pipeline                          │
│                                                                 │
│  User Input                                                     │
│     │                                                           │
│     ▼                                                           │
│  🔍 SCOUT Agent          (Complete.dev · Deploy.AI)             │
│     │  Web/news research → competitors, trends, segments        │
│     ▼                                                           │
│  📊 ANALYST Service      (local · pure Python)                  │
│     │  Normalise data → knowledge graph spec → summary          │
│     ▼                                                           │
│  ♟️  STRATEGY Agent       (Complete.dev · Deploy.AI)             │
│     │  SWOT + positioning options + GTM plan                    │
│     ▼                                                           │
│  📽️  PRESENTER Service    (local · pure Python)                  │
│     │  Markdown report + 8-slide pitch deck outline             │
│     ▼                                                           │
│  ✅ DONE  →  REST API  →  Next.js Dashboard                     │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI 0.115 · Python 3.11+ · Pydantic v2 · uvicorn |
| **Agents** | Deploy.AI / Complete.dev (OAuth2 client_credentials) |
| **Frontend** | Next.js 14 (pages router) · TypeScript · React 18 |
| **Real-time** | WebSocket push (polling fallback) |
| **Future** | FalkorDB (knowledge graph) · PostgreSQL (persistence) |

---

## 📁 Project Structure

```
athena/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI entry point, CORS, router mount
│   │   ├── core/
│   │   │   └── config.py               # pydantic-settings + .env loader
│   │   ├── models/
│   │   │   └── schemas.py              # All Pydantic models (requests, responses, enums)
│   │   ├── api/v1/
│   │   │   └── analysis.py             # REST endpoints + WebSocket + webhook router
│   │   └── services/
│   │       ├── deploy_ai_client.py     # OAuth2 + chat + message async HTTP client
│   │       ├── scout_agent.py          # Scout Agent integration (Complete.dev)
│   │       ├── analyst_service.py      # Local data transformer + graph spec builder
│   │       ├── strategy_agent.py       # Strategy Agent integration (Complete.dev)
│   │       ├── presenter_service.py    # Markdown report + pitch deck generator
│   │       └── job_store.py            # In-memory job store + pipeline orchestrator
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    ├── pages/
    │   ├── index.tsx                   # Main dashboard (form → progress → results)
    │   ├── _app.tsx
    │   └── _document.tsx
    ├── lib/
    │   └── api.ts                      # REST + WebSocket client
    ├── types/
    │   └── athena.ts                   # TypeScript types (mirrors backend schemas)
    ├── styles/
    │   └── globals.css                 # Dark ATHENA theme
    ├── package.json
    └── .env.local.example
```

---

## 🔌 API Reference

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/analysis/start` | Start pipeline, returns `job_id` |
| `GET` | `/api/v1/analysis/{job_id}/status` | Current stage, progress %, message |
| `GET` | `/api/v1/analysis/{job_id}/results` | Full results: report, deck, SWOT, GTM |
| `GET` | `/api/v1/health` | Service + component health check |
| `POST` | `/api/v1/webhook/complete-dev` | Receive Complete.dev agent callbacks |

### WebSocket

| Protocol | Path | Description |
|---|---|---|
| `WS` | `/ws/analysis/{job_id}/progress` | Real-time stage/progress push every 2s |

### Pipeline Stage Values

```
PENDING → SCOUT → ANALYST → STRATEGY → PRESENTER → DONE
                                                  ↘ ERROR
```

---

## ⚙️ Setup & Running

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in DEPLOY_AI_CLIENT_ID, DEPLOY_AI_CLIENT_SECRET, DEPLOY_AI_ORG_ID,
# SCOUT_AGENT_ID, STRATEGY_AGENT_ID
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Dashboard: http://localhost:3000

---

## 🔑 Environment Variables

### Backend (`.env`)

| Variable | Description |
|---|---|
| `DEPLOY_AI_AUTH_URL` | OAuth2 token endpoint (default provided) |
| `DEPLOY_AI_API_URL` | Core API base URL (default provided) |
| `DEPLOY_AI_CLIENT_ID` | OAuth2 client ID from Deploy.AI console |
| `DEPLOY_AI_CLIENT_SECRET` | OAuth2 client secret |
| `DEPLOY_AI_ORG_ID` | Organisation ID (`X-Org` header) |
| `SCOUT_AGENT_ID` | Complete.dev agent ID for the Scout Agent |
| `STRATEGY_AGENT_ID` | Complete.dev agent ID for the Strategy Agent |
| `REPORTS_DIR` | Output directory for `.md` reports (default `./reports`) |
| `STUB_STAGE_DELAY` | Seconds per stage in stub mode (set `0.5` for fast demo) |

### Frontend (`.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL (e.g. `http://localhost:8000`) |

---

## 📦 Pipeline Output

Once complete, ATHENA returns:

- **`report_markdown`** — Multi-section Markdown report (Executive Overview, Competitors, Trends, SWOT, Positioning, GTM Plan, Next Steps)
- **`deck_outline`** — 8-slide pitch deck outline with bullets and speaker notes
- **`swot`** — Structured SWOT (strengths / weaknesses / opportunities / threats)
- **`gtm`** — Go-to-Market plan (ICP, channels, value proposition, launch phases)
- **`competitors`** — Confirmed competitor list with confidence scores
- **`key_trends`** — High-impact market trends

---

## 🗺️ Roadmap

| ID | Feature | Status |
|---|---|---|
| TODO-9 | FalkorDB knowledge graph persistence | 🔲 Planned |
| TODO-9 | PostgreSQL job store (replace in-memory) | 🔲 Planned |
| TODO-10 | Static file serving for report download | 🔲 Planned |
| TODO-8 | Complete.dev webhook event processing | ✅ Stub ready |

---

## 📄 License

MIT — Built for the Complete AI Hackathon.
