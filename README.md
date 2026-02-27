# ⚡ ATHENA

**Autonomous Multi-Agent Market Intelligence & Strategy Platform**

> Built for the **Complete AI Hackathon** · Powered by [Deploy.AI](https://deploy.ai)

ATHENA orchestrates a four-stage AI pipeline that transforms a company name, product, or market
into a full competitive intelligence package — SWOT analysis, Go-to-Market plan, Markdown report,
and pitch deck outline — all in a single click.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ATHENA Pipeline                          │
│                                                                 │
│  User Input  (target + type: company | product | market)        │
│     │                                                           │
│     ▼                                                           │
│  🔍 SCOUT Agent          (Complete.dev · Deploy.AI)             │
│     │  Web/news research → competitors, trends, segments        │
│     ▼                                                           │
│  📊 ANALYST Service      (local · pure Python)                  │
│     │  Normalise + dedup → knowledge graph spec → summary       │
│     ▼                                                           │
│  ♟️  STRATEGY Agent       (Complete.dev · Deploy.AI)             │
│     │  SWOT + positioning options + GTM plan                    │
│     ▼                                                           │
│  📽️  PRESENTER Service    (local · pure Python)                  │
│     │  Markdown report + 8-slide pitch deck outline             │
│     ▼                                                           │
│  ✅ DONE  →  REST API  +  Static Report File  →  Next.js Dashboard│
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI 0.115 · Python 3.11+ · Pydantic v2.9 · uvicorn 0.30 |
| **Agents** | Deploy.AI / Complete.dev (OAuth2 `client_credentials`) |
| **Frontend** | Next.js 14.2 (pages router) · TypeScript 5 · React 18 |
| **Real-time** | WebSocket push (5 s fallback to polling) |
| **Container** | Docker · Docker Compose (backend + frontend + named volume) |
| **Future** | FalkorDB (knowledge graph) · PostgreSQL (persistence) |

---

## 📁 Project Structure

```
athena/
├── .gitignore
├── docker-compose.yml              # Full local stack (backend + frontend)
├── LICENSE
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py                     # FastAPI entry point, CORS, StaticFiles, logging
│       ├── core/
│       │   └── config.py               # pydantic-settings + .env loader
│       ├── models/
│       │   └── schemas.py              # All Pydantic models (requests, responses, enums)
│       ├── api/v1/
│       │   └── analysis.py             # REST endpoints + WebSocket + webhook router
│       └── services/
│           ├── deploy_ai_client.py     # OAuth2 + retry + chat + message async client
│           ├── scout_agent.py          # Scout Agent integration (Complete.dev)
│           ├── analyst_service.py      # Local transformer + knowledge graph builder
│           ├── strategy_agent.py       # Strategy Agent integration (Complete.dev)
│           ├── presenter_service.py    # Markdown report + 8-slide pitch deck generator
│           └── job_store.py            # In-memory store + TTL + lock + pipeline runner
│
└── frontend/
    ├── Dockerfile
    ├── .dockerignore
    ├── next.config.js               # reactStrictMode + /api/* rewrites
    ├── .env.local.example
    ├── package.json
    ├── tsconfig.json
    ├── pages/
    │   ├── index.tsx                # Main dashboard (form → timeline → log → results)
    │   ├── _app.tsx                 # ErrorBoundary wrapper
    │   └── _document.tsx            # Google Fonts (Inter)
    ├── lib/
    │   └── api.ts                   # REST + WebSocket client helpers
    ├── types/
    │   └── athena.ts                # TypeScript types (mirrors backend Pydantic schemas)
    └── styles/
        └── globals.css              # Dark ATHENA theme (CSS custom properties)
```

---

## 🔌 API Reference

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/analysis/start` | Start pipeline, returns `job_id` (202 Accepted) |
| `GET` | `/api/v1/analysis/{job_id}/status` | Current stage, progress %, message, error info |
| `GET` | `/api/v1/analysis/{job_id}/results` | Full results: report, deck, SWOT, GTM, competitors |
| `GET` | `/api/v1/reports/{job_id}.md` | Download raw Markdown report file |
| `GET` | `/api/v1/health` | Service + component health check |
| `POST` | `/api/v1/webhook/complete-dev` | Receive Complete.dev agent event callbacks |

### WebSocket

| Protocol | Path | Description |
|---|---|---|
| `WS` | `/ws/analysis/{job_id}/progress` | Real-time stage/progress push every 2 s |

### Pipeline Stage Values

```
PENDING → SCOUT → ANALYST → STRATEGY → PRESENTER → DONE
                                                    ↘ ERROR
```

### WebSocket Payload

```json
{
  "stage":    "ANALYST",
  "status":   "running",
  "progress": 50,
  "message":  "Analyst complete — building knowledge graph",
  "timestamp": "2026-02-27T08:00:00Z"
}
```

---

## ⚙️ Setup & Running

### 🐳 Docker Compose (recommended)

```bash
# 1. Clone and configure
git clone https://github.com/matrixNeo76/athena.git
cd athena
cp backend/.env.example backend/.env
# ✏️  Edit backend/.env: fill in DEPLOY_AI_CLIENT_ID, DEPLOY_AI_CLIENT_SECRET,
#      DEPLOY_AI_ORG_ID, SCOUT_AGENT_ID, STRATEGY_AGENT_ID

# 2. Build and start
docker compose up --build

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000  (Swagger: /docs)
```

### 🐍 Backend (manual)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in credentials (see Environment Variables section below)
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

### ⚡ Frontend (manual)

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

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `DEPLOY_AI_AUTH_URL` | `https://api-auth.dev.deploy.ai/oauth2/token` | OAuth2 token endpoint |
| `DEPLOY_AI_API_URL` | `https://core-api.dev.deploy.ai` | Core API base URL |
| `DEPLOY_AI_CLIENT_ID` | *(required)* | OAuth2 client ID from Deploy.AI console |
| `DEPLOY_AI_CLIENT_SECRET` | *(required)* | OAuth2 client secret |
| `DEPLOY_AI_ORG_ID` | *(required)* | Organisation ID (`X-Org` header) |
| `SCOUT_AGENT_ID` | *(required)* | Complete.dev agent ID for Scout |
| `STRATEGY_AGENT_ID` | *(required)* | Complete.dev agent ID for Strategy |
| `REPORTS_DIR` | `./reports` | Output directory for `.md` report files |
| `STUB_STAGE_DELAY` | `3.0` | Seconds per stage in stub/demo mode |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL |

---

## 📦 Pipeline Output

Once complete, ATHENA returns:

| Field | Type | Description |
|---|---|---|
| `report_markdown` | `string` | Multi-section Markdown report (Executive Overview, Competitors, Trends, SWOT, GTM, Next Steps) |
| `deck_outline` | `DeckSlide[]` | 8-slide pitch deck with title, bullets, speaker notes |
| `swot` | `SWOTModel` | Structured SWOT (strengths / weaknesses / opportunities / threats) |
| `gtm` | `GTMModel` | Go-to-Market plan (ICP, channels, value proposition, launch phases) |
| `competitors` | `string[]` | Deduplicated competitor list |
| `key_trends` | `string[]` | High-impact market trends |
| `report_url` | `string` | Direct URL to download the `.md` report file |

---

## 🛡️ Resilience & Safety

Implemented across the codebase to ensure production-grade reliability:

| Feature | Where | Detail |
|---|---|---|
| **Retry + backoff** | `deploy_ai_client.py` | 3 attempts, 1 s / 2 s / 4 s delays on `NetworkError` / `TimeoutException` |
| **Job TTL** | `job_store.py` | Jobs auto-expire after 24 h |
| **Memory cap** | `job_store.py` | Hard limit of 200 concurrent jobs (FIFO eviction) |
| **Concurrency lock** | `job_store.py` | `asyncio.Lock` per job — duplicate pipeline runs silently dropped |
| **Index clamp** | `job_store.py` | `recommended_positioning_index` clamped to valid range |
| **Unicode slugify** | `analyst_service.py` | `unicodedata.normalize` — handles non-ASCII company names |
| **Competitor dedup** | `analyst_service.py` | Case-insensitive deduplication before graph build |
| **React ErrorBoundary** | `_app.tsx` | Catches unhandled render errors, shows recovery UI |
| **Log history cap** | `index.tsx` | Frontend log capped at 500 entries |
| **Clipboard guard** | `index.tsx` | `navigator?.clipboard` null check for non-HTTPS contexts |

---

## 🗺️ Roadmap

| ID | Feature | Status |
|---|---|---|
| TODO-9 | FalkorDB knowledge graph persistence | 🔲 Planned |
| TODO-9 | PostgreSQL job store (replace in-memory) | 🔲 Planned |
| TODO-10 | Static file serving for report download | ✅ Complete |
| TODO-8 | Complete.dev webhook event processing | ⚠️ Stub (events logged, not yet acted on) |
| — | PDF / PPTX export | 🔲 Planned |
| — | Authentication / API keys | 🔲 Planned |

---

## 📄 License

MIT — Built for the Complete AI Hackathon.
