"""
ATHENA - In-memory job store + real pipeline runner.
TODO-6: Unified run_real_pipeline — all stages wired, stubs removed,
        per-stage error handling, results built from real data only.

Pipeline:
  SCOUT     → scout_agent.run_scout()           [TODO-3] ✓
  ANALYST   → analyst_service.run_analyst()     [TODO-5] ✓
  STRATEGY  → strategy_agent.run_strategy()     [TODO-4] ✓
  PRESENTER → presenter_service.run_presenter() [TODO-7] ✓

FIX: PipelineStage enum references updated to match renamed values
     (SCOUTING→SCOUT, ANALYZING→ANALYST, STRATEGIZING→STRATEGY,
      PRESENTING→PRESENTER, COMPLETED→DONE, FAILED→ERROR).

In production the in-memory dict will be replaced by PostgreSQL (TODO-9).
"""
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from app.models.schemas import (
    AnalystResult,
    GTMModel,
    PipelineStage,
    ScoutResult,
    StrategyResult,
    SWOTModel,
)
from app.services.analyst_service import run_analyst
from app.services.presenter_service import run_presenter
from app.services.scout_agent import run_scout
from app.services.strategy_agent import run_strategy

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# In-memory store  {job_id: dict}
# ──────────────────────────────────────────────
_jobs: dict[str, dict] = {}


# ──────────────────────────────────────────────
# Stage context manager
# ──────────────────────────────────────────────

@asynccontextmanager
async def _stage(job_id: str, stage: PipelineStage, stage_name: str):
    """
    Async context manager wrapping a single pipeline stage.
    On entry  : advances job to `stage`, emits START log.
    On success: emits COMPLETE log.
    On error  : sets job to ERROR with diagnostics, emits ERROR log, re-raises.
    """
    _advance_stage(job_id, stage)
    logger.info("[PIPELINE] ▶  stage=%-12s  job='%s'  started", stage_name, job_id)
    try:
        yield
        logger.info("[PIPELINE] ✓  stage=%-12s  job='%s'  completed", stage_name, job_id)
    except Exception as exc:                        # noqa: BLE001
        logger.error(
            "[PIPELINE] ✗  stage=%-12s  job='%s'  FAILED — %s: %s",
            stage_name, job_id, type(exc).__name__, exc,
            exc_info=True,
        )
        if job_id in _jobs:
            _jobs[job_id]["stage"]           = PipelineStage.ERROR   # FIX: was FAILED
            _jobs[job_id]["failed_at_stage"] = stage_name
            _jobs[job_id]["error"]           = f"[{type(exc).__name__}] {exc}"
            _jobs[job_id]["updated_at"]      = datetime.now(timezone.utc)
        raise


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _advance_stage(job_id: str, stage: PipelineStage) -> None:
    """Moves job to the given stage and refreshes updated_at."""
    if job_id in _jobs:
        _jobs[job_id]["stage"]      = stage
        _jobs[job_id]["updated_at"] = datetime.now(timezone.utc)


def _build_final_results(
    target: str,
    strategy_result: StrategyResult,
    analyst_result: AnalystResult,
    report_url: str,
) -> dict:
    """Builds the /results payload entirely from real pipeline outputs."""
    final_swot: Optional[SWOTModel] = (
        SWOTModel(**strategy_result.swot.model_dump())
        if strategy_result.swot else None
    )

    gtm = strategy_result.gtm_plan
    top_pos = (
        strategy_result.positioning_options[strategy_result.recommended_positioning_index].statement
        if strategy_result.positioning_options else
        f"{target}: competitive intelligence-driven positioning"
    )
    final_gtm = GTMModel(
        positioning=top_pos,
        target_segments=[s.name for s in analyst_result.segments],
        key_channels=gtm.channels if gtm else [],
        value_proposition=(gtm.value_proposition or "") if gtm else "",
        recommended_actions=[
            action
            for phase in (gtm.launch_phases if gtm else [])
            for action in phase.actions
        ][:6],
    )

    return {
        "swot":        final_swot,
        "gtm":         final_gtm,
        "competitors": [c.name for c in analyst_result.competitors],
        "key_trends":  [t.title for t in analyst_result.trends],
        "report_url":  report_url,
    }


# ──────────────────────────────────────────────
# Public store API
# ──────────────────────────────────────────────

def create_job(target: str, depth: str = "standard") -> dict:
    """Creates a new analysis job and persists it in memory."""
    job_id = str(uuid.uuid4())
    now    = datetime.now(timezone.utc)
    _jobs[job_id] = {
        "job_id":           job_id,
        "target":           target,
        "depth":            depth,
        "stage":            PipelineStage.PENDING,
        "created_at":       now,
        "updated_at":       now,
        "scout_result":     None,
        "analyst_result":   None,
        "strategy_result":  None,
        "presenter_result": None,
        "results":          None,
        "error":            None,
        "failed_at_stage":  None,
    }
    return _jobs[job_id]


def get_job(job_id: str) -> Optional[dict]:
    """Returns job dict or None if not found."""
    return _jobs.get(job_id)


def record_webhook_event(job_id: str, event: dict) -> Optional[dict]:
    """TODO-8: Appends an incoming Complete.dev webhook event to the job's event log."""
    job = _jobs.get(job_id)
    if not job:
        logger.warning("[WEBHOOK] received event for unknown job_id='%s'", job_id)
        return None

    if "webhook_events" not in _jobs[job_id]:
        _jobs[job_id]["webhook_events"] = []

    _jobs[job_id]["webhook_events"].append({
        **event,
        "received_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info(
        "[WEBHOOK] event recorded — job='%s'  event_type='%s'  agent='%s'  status='%s'  total_events=%d",
        job_id,
        event.get("event_type") or "unknown",
        event.get("agent_name") or event.get("agent_id") or "unknown",
        event.get("status") or "unknown",
        len(_jobs[job_id]["webhook_events"]),
    )

    return _jobs[job_id]


# ──────────────────────────────────────────────
# Real pipeline runner (entry point)
# ──────────────────────────────────────────────

async def run_real_pipeline(job_id: str) -> None:
    """
    Executes the full ATHENA pipeline — all stages are real calls.

    Stage flow:
      1. SCOUT     → run_scout()      → scout_result
      2. ANALYST   → run_analyst()    → analyst_result
      3. STRATEGY  → run_strategy()   → strategy_result
      4. PRESENTER → run_presenter()  → presenter_result
      5. DONE      → _build_final_results() → results dict
    """
    job = _jobs.get(job_id)
    if not job:
        logger.warning("[PIPELINE] run_real_pipeline called for unknown job_id='%s'", job_id)
        return

    target: str = job["target"]
    logger.info("[PIPELINE] ══════════ START  job='%s'  target='%s' ══════════", job_id, target)

    try:
        # ── 1. SCOUT ─────────────────────────────────────────────────────
        async with _stage(job_id, PipelineStage.SCOUT, "SCOUT"):
            scout_result = await run_scout(target=target, focus_questions=None)
            _jobs[job_id]["scout_result"] = scout_result.model_dump()
            logger.info(
                "[PIPELINE]    → %d competitors  %d trends  %d segments",
                len(scout_result.competitors),
                len(scout_result.trends),
                len(scout_result.customer_segments),
            )

        # ── 2. ANALYST ───────────────────────────────────────────────────
        async with _stage(job_id, PipelineStage.ANALYST, "ANALYST"):
            scout_obj      = ScoutResult.model_validate(_jobs[job_id]["scout_result"])
            analyst_result = await run_analyst(scout_result=scout_obj)
            _jobs[job_id]["analyst_result"] = analyst_result.model_dump()
            logger.info(
                "[PIPELINE]    → graph %d nodes  %d edges  %d pain points",
                len(analyst_result.graph_spec.nodes),
                len(analyst_result.graph_spec.edges),
                len(analyst_result.key_pain_points),
            )

        # ── 3. STRATEGY ──────────────────────────────────────────────────
        async with _stage(job_id, PipelineStage.STRATEGY, "STRATEGY"):
            analyst_obj     = AnalystResult.model_validate(_jobs[job_id]["analyst_result"])
            strategy_result = await run_strategy(analyst_result=analyst_obj)
            _jobs[job_id]["strategy_result"] = strategy_result.model_dump()
            logger.info(
                "[PIPELINE]    → %d positioning options  SWOT:%s  GTM phases:%d",
                len(strategy_result.positioning_options),
                "✓" if strategy_result.swot else "✗",
                len(strategy_result.gtm_plan.launch_phases) if strategy_result.gtm_plan else 0,
            )

        # ── 4. PRESENTER ─────────────────────────────────────────────────
        async with _stage(job_id, PipelineStage.PRESENTER, "PRESENTER"):
            strategy_obj     = StrategyResult.model_validate(_jobs[job_id]["strategy_result"])
            analyst_obj      = AnalystResult.model_validate(_jobs[job_id]["analyst_result"])
            presenter_result = await run_presenter(
                job_id=job_id,
                strategy_result=strategy_obj,
                analyst_result=analyst_obj,
            )
            _jobs[job_id]["presenter_result"] = presenter_result.model_dump()
            logger.info(
                "[PIPELINE]    → %d slides  report %d chars  path=%s",
                len(presenter_result.deck_outline),
                len(presenter_result.report_markdown),
                presenter_result.report_path,
            )

        # ── 5. DONE ───────────────────────────────────────────────────────
        _jobs[job_id]["results"] = _build_final_results(
            target=target,
            strategy_result=StrategyResult.model_validate(_jobs[job_id]["strategy_result"]),
            analyst_result=AnalystResult.model_validate(_jobs[job_id]["analyst_result"]),
            report_url=presenter_result.report_url,
        )
        _advance_stage(job_id, PipelineStage.DONE)

        logger.info(
            "[PIPELINE] ══════════ DONE  job='%s'  target='%s' ══════════",
            job_id, target,
        )

    except Exception as exc:                        # noqa: BLE001
        if _jobs.get(job_id, {}).get("stage") != PipelineStage.ERROR:
            _jobs[job_id]["stage"]           = PipelineStage.ERROR
            _jobs[job_id]["failed_at_stage"] = "UNKNOWN"
            _jobs[job_id]["error"]           = f"[{type(exc).__name__}] {exc}"
            _jobs[job_id]["updated_at"]      = datetime.now(timezone.utc)
            logger.error(
                "[PIPELINE] ✗  Unhandled error outside stage — job='%s': %s",
                job_id, exc,
                exc_info=True,
            )
