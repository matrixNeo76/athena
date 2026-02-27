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
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.analysis import router as analysis_router, webhook_router, ws_router
from app.core.config import settings
from app.models.schemas import HealthResponse

# ── Logging configuration ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Reports directory  (must exist *before* StaticFiles is mounted) ───────────────────
_reports_dir = pathlib.Path(settings.REPORTS_DIR).resolve()
_reports_dir.mkdir(parents=True, exist_ok=True)


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────────────
# FastAPI recommends the lifespan context manager over deprecated @app.on_event.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info(
        "[STARTUP] ATHENA %s — stub_mode=%s — reports_dir=%s",
        settings.APP_VERSION,
        settings.is_stub_mode,
        _reports_dir,
    )
    if settings.is_stub_mode:
        logger.warning(
            "[STARTUP] STUB MODE ACTIVE — pipeline will return demo data. "
            "Set DEPLOY_AI_CLIENT_ID in .env to enable live agents."
        )
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("[SHUTDOWN] ATHENA shutting down gracefully.")


# ── App factory ─────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "ATHENA multi-agent competitive intelligence platform.\n\n"
        "Pipeline: **Input → Scout → Analyst → Strategy → Presenter → Output**"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,   # modern FastAPI lifecycle — replaces deprecated @app.on_event
)

# ── CORS ────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────────
app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["Analysis Pipeline"])
app.include_router(webhook_router,  prefix="/api/v1/webhook",  tags=["Webhooks"])
app.include_router(ws_router,       prefix="/ws/analysis",     tags=["WebSocket"])

# ── Static file serving for Markdown reports ───────────────────────────────────────────
# Mounted AFTER all routers so /api/v1/analysis/* routes keep precedence.
app.mount(
    "/api/v1/reports",
    StaticFiles(directory=str(_reports_dir)),
    name="reports",
)


# ── Health check ─────────────────────────────────────────────────────────────────
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="System health check",
)
async def health():
    """Returns service status, component availability, and runtime config."""
    from app.services.job_store import _jobs  # lazy import to avoid circular deps
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc),
        components={
            "orchestrator":      "ok",
            "job_store":         f"ok (in-memory, {len(_jobs)} active jobs)",
            "stub_mode":         "ACTIVE — demo data" if settings.is_stub_mode else "off (live agents)",
            "scout_agent":       "stub" if settings.is_stub_mode else "ready",
            "analyst_service":   "ready",
            "strategy_agent":    "stub" if settings.is_stub_mode else "ready",
            "presenter_service": "ready",
            "report_serving":    f"ok — {_reports_dir}",
            "falkordb":          "not connected (TODO-9)",
            "postgresql":        "not connected (TODO-9)",
        },
    )


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service":   settings.APP_NAME,
        "version":   settings.APP_VERSION,
        "stub_mode": settings.is_stub_mode,
        "docs":      "/docs",
    }
