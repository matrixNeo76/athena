# ATHENA

**Autonomous Multi-Agent Market Intelligence & Strategy Platform**

> Built for the **Complete AI Hackathon** - Powered by [Deploy.AI](https://deploy.ai)

[![CI](https://github.com/matrixNeo76/athena/actions/workflows/ci.yml/badge.svg)](https://github.com/matrixNeo76/athena/actions/workflows/ci.yml)

ATHENA orchestrates a four-stage AI pipeline that transforms a company name, product, or market
into a full competitive intelligence package -- SWOT analysis, Go-to-Market plan, Markdown report,
and pitch deck outline -- all in a single click.

---

## Architecture

```
+------------------------------------------------------------------+
|                        ATHENA Pipeline                          |
|                                                                 |
|  User Input  (target + type: company | product | market)        |
|     |                                                           |
|     v                                                           |
|  SCOUT Agent          (Complete.dev / Deploy.AI)                |
|     |  Web/news research -> competitors, trends, segments       |
|     v                                                           |
|  ANALYST Service      (local / pure Python)                     |
|     |  Normalise + dedup -> knowledge graph spec -> summary     |
|     v                                                           |
|  STRATEGY Agent       (Complete.dev / Deploy.AI)                |
|     |  SWOT + positioning options + GTM plan                    |
|     v                                                           |
|  PRESENTER Service    (local / pure Python)                     |
|     |  8-section Markdown report + 8-slide pitch deck outline   |
|     v                                                           |
|  DONE  ->  REST API  +  Static Report File  ->  Next.js UI      |
+------------------------------------------------------------------+
```

### Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI 0.115 / Python 3.11+ / Pydantic v2.9 / uvicorn 0.30 |
| **Agents** | Deploy.AI / Complete.dev (OAuth2 `client_credentials`) |
| **Frontend** | Next.js 14.2 (pages router) / TypeScript 5 / React 18 |
| **Real-time** | WebSocket push (5 s fallback to polling) |
| **Container** | Docker / Docker Compose (backend + frontend + named volume) |
| **CI** | GitHub Actions (pytest + TypeScript + Docker build) |
| **Future** | FalkorDB (knowledge graph) / PostgreSQL (persistence) |

---

## Project Structure

```
athena/
+-- .github/
|   +-- workflows/
|   |   +-- ci.yml                  # Pytest + TypeScript + Docker build CI
|   +-- PULL_REQUEST_TEMPLATE.md
+-- .gitignore
+-- docker-compose.yml              # Full local stack (backend + frontend)
+-- Makefile                        # Developer convenience commands
+-- LICENSE
+-- README.md
|
+-- backend/
|   +-- Dockerfile
|   +-- requirements.txt
|   +-- .env.example
|   +-- pytest.ini
|   +-- app/
|   |   +-- main.py                 # FastAPI entry point, CORS, StaticFiles
|   |   +-- core/config.py          # pydantic-settings v2 + stub mode
|   |   +-- models/schemas.py       # All Pydantic models
|   |   +-- api/v1/analysis.py      # REST + WebSocket + webhook router
|   |   +-- services/
|   |       +-- deploy_ai_client.py # OAuth2 + retry + chat client
|   |       +-- scout_agent.py      # Scout Agent + stub mode
|   |       +-- analyst_service.py  # Local transformer + graph builder
|   |       +-- strategy_agent.py   # Strategy Agent + stub mode
|   |       +-- presenter_service.py# 8-section report + 8-slide deck
|   |       +-- job_store.py        # In-memory store + TTL + pipeline runner
|   |       +-- utils.py            # Shared helpers (extract_json)
|   +-- tests/
|       +-- conftest.py             # Shared fixtures (stub_mode, api_client)
|       +-- test_schemas.py         # Schema validation (30 tests)
|       +-- test_utils.py           # extract_json edge cases (9 tests)
|       +-- test_analyst.py         # Analyst service (13 tests)
|       +-- test_presenter.py       # Report & deck generation (18 tests)
|       +-- test_stub_pipeline.py   # End-to-end stub pipeline (20 tests)
|       +-- test_routes.py          # HTTP API contracts (48 tests)
|       +-- test_job_store.py       # Job store unit tests (29 tests)
|
+-- frontend/
    +-- Dockerfile
    +-- next.config.js              # standalone output + /api/* rewrites
    +-- .env.local.example
    +-- pages/
    |   +-- index.tsx               # Main dashboard
    |   +-- _app.tsx                # ErrorBoundary wrapper
    |   +-- _document.tsx           # Google Fonts
    |   +-- 404.tsx                 # Custom 404 page
    |   +-- 500.tsx                 # Custom 500 page
    +-- lib/api.ts                  # REST + WebSocket client
    +-- types/athena.ts             # TypeScript types (mirrors backend)
    +-- styles/globals.css          # Dark ATHENA theme
```

---

## API Reference

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/analysis/start` | Start pipeline, returns `job_id` (202 Accepted) |
| `GET` | `/api/v1/analysis/{job_id}/status` | Current stage, progress %, message, error info |
| `GET` | `/api/v1/analysis/{job_id}/results` | Full results: report, deck, SWOT, GTM, competitors |
| `GET` | `/api/v1/analysis/{job_id}/webhook-events` | List Complete.dev agent callback events |
| `GET` | `/api/v1/reports/{job_id}.md` | Download raw Markdown report file |
| `GET` | `/api/v1/health` | Service + component health check |
| `POST` | `/api/v1/webhook/complete-dev` | Receive Complete.dev agent event callbacks |

### WebSocket

| Protocol | Path | Description |
|---|---|---|
| `WS` | `/ws/analysis/{job_id}/progress` | Real-time stage/progress push every 2 s |

### Pipeline Stages

```
PENDING -> SCOUT -> ANALYST -> STRATEGY -> PRESENTER -> DONE
                                                      -> ERROR
```

---

## Setup & Running

### Docker Compose (recommended)

```bash
# Clone and configure
git clone https://github.com/matrixNeo76/athena.git
cd athena
cp backend/.env.example backend/.env
# Edit backend/.env with DEPLOY_AI_CLIENT_ID, CLIENT_SECRET, ORG_ID, AGENT IDs

# Start (requires credentials in .env)
make dev

# OR start in stub/demo mode -- no credentials needed
make dev-stub

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000/docs
```

### Backend (manual)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # fill in credentials or set STUB_MODE=true
uvicorn app.main:app --reload --port 8000
```

### Frontend (manual)

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

---

## Testing

ATHENA ships with **167 tests** across 7 test files. All tests run in stub mode -- no
Deploy.AI credentials are required.

```bash
make test            # all tests (backend + frontend checks)
make test-backend    # pytest only
make test-frontend   # TypeScript type check + ESLint
```

| File | Tests | Coverage |
|---|---|---|
| `test_schemas.py` | 30 | Pydantic model validation |
| `test_utils.py` | 9 | `extract_json()` edge cases |
| `test_analyst.py` | 13 | Analyst service transformations |
| `test_presenter.py` | 18 | 8-section report & 8-slide deck |
| `test_stub_pipeline.py` | 20 | End-to-end Scout->Analyst->Strategy->Presenter |
| `test_routes.py` | 48 | HTTP API endpoint contracts |
| `test_job_store.py` | 29 | Job store operations & TTL eviction |
| **Total** | **167** | |

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `DEPLOY_AI_AUTH_URL` | `https://api-auth.dev.deploy.ai/oauth2/token` | OAuth2 token endpoint |
| `DEPLOY_AI_API_URL` | `https://core-api.dev.deploy.ai` | Core API base URL |
| `DEPLOY_AI_CLIENT_ID` | *(required for live)* | OAuth2 client ID |
| `DEPLOY_AI_CLIENT_SECRET` | *(required for live)* | OAuth2 client secret |
| `DEPLOY_AI_ORG_ID` | *(required for live)* | Organisation ID (`X-Org` header) |
| `SCOUT_AGENT_ID` | *(required for live)* | Complete.dev agent ID for Scout |
| `STRATEGY_AGENT_ID` | *(required for live)* | Complete.dev agent ID for Strategy |
| `REPORTS_DIR` | `./reports` | Output directory for `.md` report files |
| `STUB_MODE` | `false` | Set `true` for demo data without credentials |

> **Stub Mode**: Auto-activates when `DEPLOY_AI_CLIENT_ID` is empty. Returns realistic
> demo data for every pipeline stage. Ideal for local development and CI.

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL |

---

## Pipeline Output

| Field | Type | Description |
|---|---|---|
| `report_markdown` | `string` | 8-section Markdown report |
| `deck_outline` | `DeckSlide[]` | 8-slide pitch deck with bullets + speaker notes |
| `swot` | `SWOTModel` | Structured SWOT (strengths/weaknesses/opportunities/threats) |
| `gtm` | `GTMModel` | GTM plan (ICP, channels, value proposition, launch phases) |
| `competitors` | `string[]` | Deduplicated competitor list |
| `key_trends` | `string[]` | High-impact market trends |
| `report_url` | `string` | Direct URL to download the `.md` report |

---

## Resilience & Safety

| Feature | Where | Detail |
|---|---|---|
| **Retry + backoff** | `deploy_ai_client.py` | 3 attempts, 1s/2s/4s on NetworkError/TimeoutException |
| **Job TTL** | `job_store.py` | Jobs auto-expire after 24 h |
| **Memory cap** | `job_store.py` | Hard limit of 200 concurrent jobs (FIFO eviction) |
| **Concurrency lock** | `job_store.py` | asyncio.Lock per job -- duplicate runs dropped |
| **Index clamp** | `job_store.py` | recommended_positioning_index clamped to valid range |
| **Unicode slugify** | `analyst_service.py` | unicodedata.normalize handles non-ASCII names |
| **Competitor dedup** | `analyst_service.py` | Case-insensitive deduplication before graph build |
| **Non-fatal I/O** | `presenter_service.py` | Disk write errors don't crash the pipeline |
| **React ErrorBoundary** | `_app.tsx` | Catches unhandled render errors |
| **Log history cap** | `index.tsx` | Frontend log capped at 500 entries |
| **WS fallback** | `index.tsx` | 5s WebSocket timeout, fallback to 2s polling |

---

## Roadmap

| Feature | Status |
|---|---|
| FalkorDB knowledge graph persistence | Planned |
| PostgreSQL job store (replace in-memory) | Planned |
| Complete.dev webhook event processing | Stub (events logged, not acted on) |
| PDF / PPTX export | Planned |
| Authentication / API keys | Planned |
| Rate limiting | Planned |

---

## License

MIT -- Built for the Complete AI Hackathon.
