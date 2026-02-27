"""
ATHENA - Analysis, Webhook and WebSocket routers.

Routers exported (mounted in main.py with correct prefixes):
  router         → prefix /api/v1/analysis
    POST   /api/v1/analysis/start
    GET    /api/v1/analysis/{job_id}/status
    GET    /api/v1/analysis/{job_id}/results
    GET    /api/v1/analysis/{job_id}/webhook-events   ← NEW (LATS pass 4)

  webhook_router → prefix /api/v1/webhook
    POST   /api/v1/webhook/complete-dev          [TODO-8] ✓

  ws_router      → prefix /ws/analysis
    WS     /ws/analysis/{job_id}/progress

FIX: PipelineStage references updated (COMPLETED→DONE, FAILED→ERROR).
FIX: /status now returns 'message' (was 'label') + 'status', 'error_message', 'failed_at_stage'.
FIX: /results now includes 'presenter_result' and 'status' fields for frontend.
FIX: WS payload now includes 'message' alias + 'status' string.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect

from app.models.schemas import (
    AnalysisStartRequest,
    AnalysisStartResponse,
    AnalysisStatusResponse,
    AnalysisResultsResponse,
    CompleteDevWebhookPayload,
    WebhookEventResponse,
    PresenterResult,
    PipelineStage,
    STAGE_PROGRESS,
    STAGE_LABELS,
)
from app.services.job_store import (
    create_job,
    get_job,
    get_webhook_events,
    run_real_pipeline,
    record_webhook_event,
)

logger = logging.getLogger(__name__)

# Core pipeline routes  (prefix: /api/v1/analysis)
router = APIRouter()

# Webhook routes        (prefix: /api/v1/webhook)
webhook_router = APIRouter()

# WebSocket routes      (prefix: /ws/analysis)
ws_router = APIRouter()


# ──────────────────────────────────────────────
# POST /api/v1/analysis/start
# ──────────────────────────────────────────────

@router.post(
    "/start",
    response_model=AnalysisStartResponse,
    status_code=202,
    summary="Start a new intelligence analysis pipeline",
)
async def start_analysis(
    body: AnalysisStartRequest,
    background_tasks: BackgroundTasks,
):
    job = create_job(target=body.target, depth=body.depth or "standard")
    background_tasks.add_task(run_real_pipeline, job["job_id"])
    return AnalysisStartResponse(
        job_id=job["job_id"],
        target=job["target"],
        status="pending",
        stage=PipelineStage.PENDING,
        message=f"Analysis started for '{body.target}'. Poll /status for progress.",
        created_at=job["created_at"],
    )


# ──────────────────────────────────────────────
# GET /api/v1/analysis/{job_id}/status
# ──────────────────────────────────────────────

@router.get(
    "/{job_id}/status",
    response_model=AnalysisStatusResponse,
    summary="Poll the current pipeline stage and progress",
)
async def get_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    stage: PipelineStage = job["stage"]

    if stage == PipelineStage.DONE:
        status_str = "done"
    elif stage == PipelineStage.ERROR:
        status_str = "error"
    elif stage == PipelineStage.PENDING:
        status_str = "pending"
    else:
        status_str = "running"

    return AnalysisStatusResponse(
        job_id=job_id,
        target=job["target"],
        stage=stage,
        status=status_str,
        progress=STAGE_PROGRESS[stage],
        message=STAGE_LABELS[stage],
        error_message=job.get("error"),
        failed_at_stage=job.get("failed_at_stage"),
        started_at=job.get("created_at"),
        completed_at=job.get("updated_at") if stage == PipelineStage.DONE else None,
        updated_at=job["updated_at"],
    )


# ──────────────────────────────────────────────
# GET /api/v1/analysis/{job_id}/results
# ──────────────────────────────────────────────

@router.get(
    "/{job_id}/results",
    response_model=AnalysisResultsResponse,
    summary="Retrieve final analysis results (report, deck, SWOT, GTM, competitors, trends)",
)
async def get_results(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    stage: PipelineStage = job["stage"]

    if stage not in (PipelineStage.DONE, PipelineStage.ERROR):
        return AnalysisResultsResponse(
            job_id=job_id,
            target=job["target"],
            stage=stage,
            status="running",
            message=f"Pipeline in progress ({STAGE_LABELS[stage]}). Results not yet available.",
        )

    if stage == PipelineStage.ERROR:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed for job '{job_id}': {job.get('error', 'unknown error')}",
        )

    results = job["results"] or {}

    presenter_result: PresenterResult | None = None
    if job.get("presenter_result"):
        try:
            presenter_result = PresenterResult.model_validate(job["presenter_result"])
        except Exception as exc:
            logger.warning("[API] Could not reconstruct PresenterResult: %s", exc)

    return AnalysisResultsResponse(
        job_id=job_id,
        target=job["target"],
        stage=PipelineStage.DONE,
        status="done",
        presenter_result=presenter_result,
        swot=results.get("swot"),
        gtm=results.get("gtm"),
        competitors=results.get("competitors"),
        key_trends=results.get("key_trends"),
        report_url=results.get("report_url"),
        completed_at=job["updated_at"],
        message="Analysis complete. Full intelligence package available.",
    )


# ──────────────────────────────────────────────
# GET /api/v1/analysis/{job_id}/webhook-events
# ──────────────────────────────────────────────

@router.get(
    "/{job_id}/webhook-events",
    summary="List all Complete.dev webhook events recorded for a pipeline job",
)
async def get_job_webhook_events(job_id: str):
    """
    Returns the ordered list of webhook events received from Complete.dev
    for the given job.  Useful for debugging agent callback behaviour.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    events = get_webhook_events(job_id) or []
    return {
        "job_id":       job_id,
        "event_count":  len(events),
        "events":       events,
    }


# ──────────────────────────────────────────────
# POST /api/v1/webhook/complete-dev  [TODO-8] ✓
# ──────────────────────────────────────────────

@webhook_router.post(
    "/complete-dev",
    response_model=WebhookEventResponse,
    summary="Receive agent callbacks from Complete.dev",
    tags=["Webhooks"],
)
async def webhook_complete_dev(payload: CompleteDevWebhookPayload) -> WebhookEventResponse:
    logger.info(
        "[WEBHOOK] incoming event — job_id='%s'  event_type='%s'  agent='%s'  status='%s'",
        payload.job_id or "—",
        payload.event_type or "—",
        payload.agent_name or payload.agent_id or "—",
        payload.status or "—",
    )

    recorded = False
    if payload.job_id:
        updated_job = record_webhook_event(
            job_id=payload.job_id,
            event=payload.model_dump(exclude_none=True),
        )
        recorded = updated_job is not None
    else:
        logger.warning(
            "[WEBHOOK] payload contains no job_id. Keys: %s",
            list(payload.model_dump(exclude_none=True).keys()),
        )

    return WebhookEventResponse(
        ok=True,
        job_id=payload.job_id,
        event_type=payload.event_type,
        recorded=recorded,
        detail=(
            f"Event recorded on job '{payload.job_id}'."
            if recorded else
            "Event received but not associated with any job (no job_id in payload)."
        ),
    )


# ──────────────────────────────────────────────
# WS /ws/analysis/{job_id}/progress
# ──────────────────────────────────────────────

@ws_router.websocket("/{job_id}/progress")
async def ws_progress(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time pipeline progress.
    Pushes a status update every 2 seconds until job is terminal (DONE or ERROR).
    FIX: payload includes 'message' alias and 'status' string for frontend compatibility.
    """
    await websocket.accept()

    try:
        while True:
            job = get_job(job_id)
            if not job:
                await websocket.send_text(
                    json.dumps({"error": f"Job '{job_id}' not found", "stage": "ERROR"})
                )
                break

            stage: PipelineStage = job["stage"]

            if stage == PipelineStage.DONE:
                status_str = "done"
            elif stage == PipelineStage.ERROR:
                status_str = "error"
            elif stage == PipelineStage.PENDING:
                status_str = "pending"
            else:
                status_str = "running"

            label = STAGE_LABELS[stage]

            payload = {
                "job_id":    job_id,
                "stage":     stage.value,
                "progress":  STAGE_PROGRESS[stage],
                "label":     label,
                "message":   label,          # FIX: alias for frontend
                "status":    status_str,     # FIX: new field
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send_text(json.dumps(payload))

            if stage in (PipelineStage.DONE, PipelineStage.ERROR):
                break

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        pass
