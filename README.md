# ATHENA

Autonomous multi-agent market & competitive intelligence platform for the Complete AI Hackathon.

Built with:
- Complete.dev agents (Scout, Strategy)
- FastAPI orchestrator (backend)
- Future: FalkorDB + PostgreSQL for knowledge graph and structured data


📁 Struttura cartelle
backend/
├── app/
│   ├── main.py                  # Entry point FastAPI, CORS, router mount, /health
│   ├── core/config.py           # Settings via pydantic-settings + .env
│   ├── models/schemas.py        # Tutti i Pydantic models (request/response + enums)
│   ├── services/job_store.py    # In-memory store + stub pipeline async
│   └── api/v1/analysis.py       # Tutti gli endpoint + WebSocket
├── requirements.txt
└── .env.example
🔌 Endpoint implementati
Method	Path	Descrizione
POST	/api/v1/analysis/start	Crea job, lancia pipeline in background, ritorna job_id
GET	/api/v1/analysis/{job_id}/status	Fase corrente + progress % + label
GET	/api/v1/analysis/{job_id}/results	SWOT, GTM, competitors, trends, report URL
GET	/api/v1/health	Status tutti i componenti
POST	/api/v1/analysis/webhook/complete-dev	Stub per callback Complete.dev agents
WS	/ws/analysis/{job_id}/progress	Push real-time ogni 2s
⚙️ Come avviare
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
# Swagger: http://localhost:8000/docs
Ogni stage dura STUB_STAGE_DELAY secondi (default 3s) — impostalo a 0.5 nel .env per demo veloci. I TODO nel codice segnano esattamente dove inserire le chiamate reali agli agent Complete.dev.
