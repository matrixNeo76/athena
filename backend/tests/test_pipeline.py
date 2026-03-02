"""
Integration tests for the LATS Pipeline Orchestrator.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.pipeline_orchestrator import LATSPipelineOrchestrator, create_orchestrator


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _make_mock_scout():
    m = MagicMock()
    m.competitors = [MagicMock() for _ in range(5)]
    m.market_trends = [MagicMock() for _ in range(5)]
    m.customer_segments = [MagicMock() for _ in range(3)]
    m.data_quality = {"completeness_score": 0.9}
    return m


def _make_mock_analyst():
    m = MagicMock()
    m.knowledge_graph = MagicMock()
    m.summary = "Mock analyst summary"
    return m


def _make_mock_strategy():
    m = MagicMock()
    class SWOT:
        strengths = [MagicMock() for _ in range(4)]
        weaknesses = [MagicMock() for _ in range(3)]
        opportunities = [MagicMock() for _ in range(4)]
        threats = [MagicMock() for _ in range(3)]
    m.swot = SWOT()
    m.gtm = MagicMock()
    m.positioning_options = [MagicMock() for _ in range(3)]
    m.immediate_actions = [MagicMock() for _ in range(4)]
    return m


def _make_mock_presenter():
    m = MagicMock()
    m.report_markdown = "# Test Report"
    m.deck_slides = []
    return m


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestLATSPipelineOrchestrator:

    @patch("app.services.pipeline_orchestrator.run_scout", new_callable=AsyncMock)
    @patch("app.services.pipeline_orchestrator.run_analyst", new_callable=AsyncMock)
    @patch("app.services.pipeline_orchestrator.run_strategy", new_callable=AsyncMock)
    @patch("app.services.pipeline_orchestrator.run_presenter", new_callable=AsyncMock)
    async def test_full_pipeline_success(
        self, mock_presenter, mock_strategy, mock_analyst, mock_scout
    ):
        """Pipeline should complete and return all stage results."""
        mock_scout.return_value = _make_mock_scout()
        mock_analyst.return_value = _make_mock_analyst()
        mock_strategy.return_value = _make_mock_strategy()
        mock_presenter.return_value = _make_mock_presenter()

        orchestrator = LATSPipelineOrchestrator(n_candidates=1, use_lats=False)
        result = await orchestrator.run(job_id="pipe-001", target="OpenAI", depth="quick")

        assert "scout" in result
        assert "analyst" in result
        assert "strategy" in result
        assert "presenter" in result
        assert result["job_id"] == "pipe-001"
        assert result["target"] == "OpenAI"

    @patch("app.services.pipeline_orchestrator.run_scout", new_callable=AsyncMock)
    @patch("app.services.pipeline_orchestrator.run_analyst", new_callable=AsyncMock)
    @patch("app.services.pipeline_orchestrator.run_strategy", new_callable=AsyncMock)
    @patch("app.services.pipeline_orchestrator.run_presenter", new_callable=AsyncMock)
    async def test_status_callback_invoked(
        self, mock_presenter, mock_strategy, mock_analyst, mock_scout
    ):
        """Status callback should be called for each pipeline stage."""
        mock_scout.return_value = _make_mock_scout()
        mock_analyst.return_value = _make_mock_analyst()
        mock_strategy.return_value = _make_mock_strategy()
        mock_presenter.return_value = _make_mock_presenter()

        stages_received = []

        async def callback(stage, progress, message):
            stages_received.append(stage)

        orchestrator = LATSPipelineOrchestrator(n_candidates=1, use_lats=False)
        await orchestrator.run(
            job_id="pipe-002", target="Anthropic",
            depth="quick", status_callback=callback,
        )

        assert "SCOUT" in stages_received
        assert "ANALYST" in stages_received
        assert "STRATEGY" in stages_received
        assert "PRESENTER" in stages_received
        assert "DONE" in stages_received

    @patch("app.services.pipeline_orchestrator.run_scout", new_callable=AsyncMock)
    async def test_scout_failure_raises_error(self, mock_scout):
        """If Scout returns None, the pipeline should raise RuntimeError."""
        mock_scout.return_value = None
        orchestrator = LATSPipelineOrchestrator(n_candidates=1, use_lats=False)
        with pytest.raises(RuntimeError, match="Scout stage failed"):
            await orchestrator.run(job_id="pipe-003", target="Fail Corp")

    @patch("app.services.pipeline_orchestrator.run_scout", new_callable=AsyncMock)
    @patch("app.services.pipeline_orchestrator.run_analyst", new_callable=AsyncMock)
    @patch("app.services.pipeline_orchestrator.run_strategy", new_callable=AsyncMock)
    async def test_strategy_failure_raises_error(
        self, mock_strategy, mock_analyst, mock_scout
    ):
        """If Strategy returns None, the pipeline should raise RuntimeError."""
        mock_scout.return_value = _make_mock_scout()
        mock_analyst.return_value = _make_mock_analyst()
        mock_strategy.return_value = None
        orchestrator = LATSPipelineOrchestrator(n_candidates=1, use_lats=False)
        with pytest.raises(RuntimeError, match="Strategy stage failed"):
            await orchestrator.run(job_id="pipe-004", target="Fail Corp")

    async def test_lats_traces_in_results(self):
        """Results should always include lats_traces dict."""
        with (
            patch("app.services.pipeline_orchestrator.run_scout",
                  new_callable=AsyncMock, return_value=_make_mock_scout()),
            patch("app.services.pipeline_orchestrator.run_analyst",
                  new_callable=AsyncMock, return_value=_make_mock_analyst()),
            patch("app.services.pipeline_orchestrator.run_strategy",
                  new_callable=AsyncMock, return_value=_make_mock_strategy()),
            patch("app.services.pipeline_orchestrator.run_presenter",
                  new_callable=AsyncMock, return_value=_make_mock_presenter()),
        ):
            orchestrator = LATSPipelineOrchestrator(n_candidates=1, use_lats=False)
            result = await orchestrator.run(job_id="pipe-005", target="Meta")
            assert "lats_traces" in result
            assert "scout" in result["lats_traces"]
            assert "strategy" in result["lats_traces"]


class TestCreateOrchestrator:
    def test_create_quick(self):
        o = create_orchestrator("quick")
        assert isinstance(o, LATSPipelineOrchestrator)
        assert o._scout_engine.n_candidates == 1

    def test_create_standard(self):
        o = create_orchestrator("standard")
        assert o._scout_engine.n_candidates == 2

    def test_create_deep(self):
        o = create_orchestrator("deep")
        assert o._scout_engine.n_candidates == 3
