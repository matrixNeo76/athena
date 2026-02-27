"""
ATHENA LATS-Enhanced Pipeline Orchestrator
==========================================
Wraps the four-stage pipeline (Scout -> Analyst -> Strategy -> Presenter)
with LATS tree search for improved output quality.

Drop-in replacement for the linear run_real_pipeline used in job_store.py.
Enabled via LATS_ENABLED=true environment variable.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from app.services.lats_engine import (
    LATSEngine,
    SearchTrace,
    heuristic_scout_value,
    heuristic_strategy_value,
    heuristic_reflect,
)
from app.services.scout_agent import run_scout
from app.services.analyst_service import run_analyst
from app.services.strategy_agent import run_strategy
from app.services.presenter_service import run_presenter
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LATSPipelineOrchestrator:
    """
    LATS-enhanced orchestrator for the ATHENA intelligence pipeline.

    Wraps Scout and Strategy stages with tree search to improve output
    quality through reflection and candidate selection. Analyst and
    Presenter stages are deterministic and run linearly.

    Pipeline::

        Scout (LATS) --> Analyst --> Strategy (LATS) --> Presenter

    Args:
        n_candidates:       Parallel candidates per LATS expansion.
        quality_threshold:  Score threshold for early exit (0-1).
        max_depth:          Max reflection iterations per stage.
        use_lats:           Master switch to disable LATS (linear fallback).
    """

    def __init__(
        self,
        n_candidates: int = 2,
        quality_threshold: float = 0.65,
        max_depth: int = 2,
        use_lats: bool = True,
    ) -> None:
        self.use_lats = use_lats
        self._scout_engine = LATSEngine(
            n_candidates=n_candidates,
            max_depth=max_depth,
            quality_threshold=quality_threshold,
        )
        self._strategy_engine = LATSEngine(
            n_candidates=n_candidates,
            max_depth=max_depth,
            quality_threshold=quality_threshold,
        )

    # ── Public API ────────────────────────────

    async def run(
        self,
        job_id: str,
        target: str,
        depth: str = "standard",
        status_callback: Optional[Callable] = None,
    ) -> dict:
        """
        Execute the full LATS-enhanced pipeline.

        Args:
            job_id:          Unique job identifier.
            target:          Company / product / market name.
            depth:           'quick' | 'standard' | 'deep'
            status_callback: async callable(stage, progress, message)

        Returns:
            Dict with scout, analyst, strategy, presenter results
            and per-stage LATS trace metadata.
        """
        results: dict[str, Any] = {
            "job_id": job_id,
            "target": target,
            "lats_traces": {},
        }

        # Adjust LATS intensity based on depth
        if depth == "quick":
            self._scout_engine.n_candidates = 1
            self._strategy_engine.n_candidates = 1
        elif depth == "deep":
            self._scout_engine.n_candidates = 3
            self._strategy_engine.n_candidates = 3

        # ── Stage 1: Scout ─────────────────────────
        await self._emit(status_callback, "SCOUT", 10, f"Gathering intelligence on {target}...")

        if self.use_lats and depth != "quick":
            scout_result, scout_score, scout_trace = await self._scout_engine.search(
                agent_fn=lambda _p: run_scout(target),
                value_fn=heuristic_scout_value,
                reflect_fn=heuristic_reflect,
                initial_prompt=target,
                job_id=job_id,
            )
            results["lats_traces"]["scout"] = scout_trace.to_dict()
            logger.info("[Orchestrator][%s] Scout LATS score=%.3f", job_id, scout_score)
        else:
            scout_result = await run_scout(target)
            results["lats_traces"]["scout"] = {"score": 1.0, "lats_used": False}

        if scout_result is None:
            raise RuntimeError(f"[Orchestrator][{job_id}] Scout stage failed")

        results["scout"] = scout_result
        await self._emit(status_callback, "ANALYST", 35, "Structuring intelligence data...")

        # ── Stage 2: Analyst ───────────────────────
        analyst_result = await run_analyst(scout_result)
        if analyst_result is None:
            raise RuntimeError(f"[Orchestrator][{job_id}] Analyst stage failed")

        results["analyst"] = analyst_result
        await self._emit(status_callback, "STRATEGY", 55, "Generating strategic analysis...")

        # ── Stage 3: Strategy ──────────────────────
        if self.use_lats and depth != "quick":
            strategy_result, strategy_score, strategy_trace = await self._strategy_engine.search(
                agent_fn=lambda _p: run_strategy(analyst_result),
                value_fn=heuristic_strategy_value,
                reflect_fn=heuristic_reflect,
                initial_prompt=str(analyst_result),
                job_id=job_id,
            )
            results["lats_traces"]["strategy"] = strategy_trace.to_dict()
            logger.info("[Orchestrator][%s] Strategy LATS score=%.3f", job_id, strategy_score)
        else:
            strategy_result = await run_strategy(analyst_result)
            results["lats_traces"]["strategy"] = {"score": 1.0, "lats_used": False}

        if strategy_result is None:
            raise RuntimeError(f"[Orchestrator][{job_id}] Strategy stage failed")

        results["strategy"] = strategy_result
        await self._emit(status_callback, "PRESENTER", 80, "Generating reports and deck...")

        # ── Stage 4: Presenter ─────────────────────
        presenter_result = await run_presenter(
            scout_result=scout_result,
            analyst_result=analyst_result,
            strategy_result=strategy_result,
        )
        results["presenter"] = presenter_result
        await self._emit(status_callback, "DONE", 100, "Analysis complete!")

        logger.info(
            "[Orchestrator][%s] Pipeline complete | depth=%s",
            job_id, depth,
        )
        return results

    # ── Private helpers ───────────────────────

    @staticmethod
    async def _emit(
        callback: Optional[Callable],
        stage: str,
        progress: int,
        message: str,
    ) -> None:
        """Safely invoke the status callback."""
        if callback:
            try:
                await callback(stage=stage, progress=progress, message=message)
            except Exception as exc:
                logger.warning("[Orchestrator] status callback error: %s", exc)


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────

def create_orchestrator(depth: str = "standard") -> LATSPipelineOrchestrator:
    """
    Create an orchestrator configured for the given depth.

    Args:
        depth: 'quick' | 'standard' | 'deep'
    """
    lats_enabled = getattr(settings, "lats_enabled", True)
    config = {
        "quick":    {"n_candidates": 1, "max_depth": 1, "quality_threshold": 0.50},
        "standard": {"n_candidates": 2, "max_depth": 2, "quality_threshold": 0.65},
        "deep":     {"n_candidates": 3, "max_depth": 3, "quality_threshold": 0.75},
    }.get(depth, {"n_candidates": 2, "max_depth": 2, "quality_threshold": 0.65})

    return LATSPipelineOrchestrator(**config, use_lats=lats_enabled)
