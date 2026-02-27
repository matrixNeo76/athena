"""
ATHENA Intelligence Orchestrator
FastAPI entry point — mounts all routers, configures CORS, logging,
and static file serving for generated reports.

Run locally:
    uvicorn app.main:app --reload --port 8000

Environment variables (copy .env.example → .env):
    See .env.example
"""
import logging
import pathlib
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.analysis import router as analysis_router, webhook_router, ws_router
from app.core.config import settings
from app.models.schemas import HealthResponse

# ── Logging configuration ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Reports directory  (must exist *before* StaticFiles is mounted) ───────────
# TODO-10 ✓ — static file serving for generated Markdown reports
_reports_dir = pathlib.Path(settings.REPORTS_DIR).resolve()
_reports_dir.mkdir(parents=True, exist_ok=True)
logger.info("[STARTUP] Reports directory: %s", _reports_dir)

# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "ATHENA multi-agent competitive intelligence platform.\n\n"
        "Pipeline: **Input → Scout → Analyst → Strategy → Presenter → Output**"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(
    analysis_router,
    prefix="/api/v1/analysis",
    tags=["Analysis Pipeline"],
)
app.include_router(
    webhook_router,
    prefix="/api/v1/webhook",
    tags=["Webhooks"],
)
app.include_router(
    ws_router,
    prefix="/ws/analysis",
    tags=["WebSocket"],
)

# ── Static file serving for Markdown reports  (TODO-10 ✓) ─────────────────────
# Mounted AFTER all routers so /api/v1/analysis/* routes keep precedence.
app.mount(
    "/api/v1/reports",
    StaticFiles(directory=str(_reports_dir)),
    name="reports",
)

# ── Health check ──────────────────────────────────────────────────────────────
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="System health check",
)
async def health():
    """Returns service status and component availability."""
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc),
        components={
            "orchestrator":      "ok",
            "job_store":         "ok (in-memory)",
            "scout_agent":       "ready",
            "analyst_service":   "ready",
            "strategy_agent":    "ready",
            "presenter_service": "ready",
            "report_serving":    f"ok — {_reports_dir}",
            "falkordb":          "not connected (TODO-9)",
            "postgresql":        "not connected (TODO-9)",
        },
    )


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.APP_NAME,
        "docs":    "/docs",
        "version": settings.APP_VERSION,
    }
