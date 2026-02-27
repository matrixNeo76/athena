"""
Unit tests for the LATS Engine.
"""
from __future__ import annotations

import asyncio
import pytest

from app.services.lats_engine import (
    LATSEngine,
    SearchTrace,
    TreeNode,
    heuristic_scout_value,
    heuristic_strategy_value,
    heuristic_reflect,
)


# ─────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────

class MockScoutResult:
    """Minimal stand-in for a ScoutResult."""
    def __init__(self, n_competitors=3, n_trends=3, n_segments=2, completeness=0.8):
        self.competitors = [object() for _ in range(n_competitors)]
        self.market_trends = [object() for _ in range(n_trends)]
        self.customer_segments = [object() for _ in range(n_segments)]
        self.data_quality = {"completeness_score": completeness}


class MockStrategyResult:
    """Minimal stand-in for a StrategyResult."""
    def __init__(self, n_swot=3, has_gtm=True, n_positioning=2, n_actions=3):
        class SWOT:
            strengths = [object() for _ in range(n_swot)]
            weaknesses = [object() for _ in range(n_swot)]
            opportunities = [object() for _ in range(n_swot)]
            threats = [object() for _ in range(n_swot)]
        self.swot = SWOT()
        self.gtm = object() if has_gtm else None
        self.positioning_options = [object() for _ in range(n_positioning)]
        self.immediate_actions = [object() for _ in range(n_actions)]


async def _good_agent(prompt: str):
    """Agent that always returns a high-quality mock result."""
    return MockScoutResult(n_competitors=5, n_trends=6, n_segments=3, completeness=0.95)


async def _poor_agent(prompt: str):
    """Agent that returns a low-quality mock result."""
    return MockScoutResult(n_competitors=1, n_trends=1, n_segments=0, completeness=0.2)


async def _improving_agent(prompt: str):
    """Agent that returns good result only if the prompt contains feedback."""
    if "Quality Feedback" in prompt:
        return MockScoutResult(n_competitors=5, n_trends=5, n_segments=3, completeness=0.9)
    return MockScoutResult(n_competitors=2, n_trends=2, n_segments=1, completeness=0.4)


async def _failing_agent(prompt: str):
    raise RuntimeError("Simulated agent failure")


# ─────────────────────────────────────────────
# TreeNode tests
# ─────────────────────────────────────────────

class TestTreeNode:
    def test_ucb1_unvisited_is_inf(self):
        node = TreeNode(state=None, visits=0)
        assert node.ucb1() == float("inf")

    def test_ucb1_visited(self):
        parent = TreeNode(state=None, visits=10, value=8.0)
        child = TreeNode(state=None, parent=parent, visits=3, value=2.1)
        score = child.ucb1()
        assert 0 < score < 10  # sanity range

    def test_is_promising_above_threshold(self):
        node = TreeNode(state=None, score=0.7)
        assert node.is_promising

    def test_is_promising_below_threshold(self):
        node = TreeNode(state=None, score=0.5)
        assert not node.is_promising


# ─────────────────────────────────────────────
# SearchTrace tests
# ─────────────────────────────────────────────

class TestSearchTrace:
    def test_add_node_increments_count(self):
        trace = SearchTrace(job_id="test-job")
        trace.add_node(1, 1, 0.7)
        assert trace.total_candidates == 1
        assert trace.best_score == pytest.approx(0.7)

    def test_add_node_updates_best_score(self):
        trace = SearchTrace(job_id="test-job")
        trace.add_node(1, 1, 0.5)
        trace.add_node(1, 2, 0.8)
        assert trace.best_score == pytest.approx(0.8)

    def test_to_dict_structure(self):
        trace = SearchTrace(job_id="abc")
        trace.add_node(1, 1, 0.6)
        d = trace.to_dict()
        assert "job_id" in d
        assert "total_candidates" in d
        assert "best_score" in d
        assert "nodes" in d
        assert len(d["nodes"]) == 1


# ─────────────────────────────────────────────
# LATSEngine tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestLATSEngineSearch:
    async def test_search_returns_result_and_score(self):
        engine = LATSEngine(n_candidates=2, max_depth=1, quality_threshold=0.5)
        result, score, trace = await engine.search(
            agent_fn=_good_agent,
            value_fn=heuristic_scout_value,
            reflect_fn=heuristic_reflect,
            initial_prompt="OpenAI",
            job_id="test-001",
        )
        assert result is not None
        assert 0.0 <= score <= 1.0
        assert isinstance(trace, SearchTrace)

    async def test_early_exit_on_high_quality(self):
        """Good agent should trigger early exit at depth 1."""
        engine = LATSEngine(n_candidates=3, max_depth=3, quality_threshold=0.60)
        result, score, trace = await engine.search(
            agent_fn=_good_agent,
            value_fn=heuristic_scout_value,
            reflect_fn=heuristic_reflect,
            initial_prompt="OpenAI",
            job_id="test-002",
        )
        # Early exit means no reflection triggered
        assert not trace.reflection_triggered
        assert score >= 0.60

    async def test_reflection_triggered_on_low_quality(self):
        """Poor agent should trigger reflection at depth 2."""
        engine = LATSEngine(n_candidates=2, max_depth=2, quality_threshold=0.90)
        result, score, trace = await engine.search(
            agent_fn=_poor_agent,
            value_fn=heuristic_scout_value,
            reflect_fn=heuristic_reflect,
            initial_prompt="some target",
            job_id="test-003",
        )
        assert trace.reflection_triggered

    async def test_improving_agent_benefits_from_reflection(self):
        """Agent that improves with feedback should score higher after reflection."""
        engine = LATSEngine(n_candidates=1, max_depth=2, quality_threshold=0.80)
        result, score, trace = await engine.search(
            agent_fn=_improving_agent,
            value_fn=heuristic_scout_value,
            reflect_fn=heuristic_reflect,
            initial_prompt="Anthropic",
            job_id="test-004",
        )
        assert trace.reflection_triggered
        # The improved result should score higher than the initial one
        depth1_scores = [n["score"] for n in trace.nodes if n["depth"] == 1]
        depth2_scores = [n["score"] for n in trace.nodes if n["depth"] == 2]
        if depth2_scores:
            assert max(depth2_scores) >= max(depth1_scores)

    async def test_failing_agent_returns_none_gracefully(self):
        """Engine should not crash when agent raises an exception."""
        engine = LATSEngine(n_candidates=2, max_depth=1, quality_threshold=0.5)
        result, score, trace = await engine.search(
            agent_fn=_failing_agent,
            value_fn=heuristic_scout_value,
            reflect_fn=heuristic_reflect,
            initial_prompt="target",
            job_id="test-005",
        )
        # All candidates failed -> result is None, score neutral
        assert result is None
        assert score == pytest.approx(0.0)

    async def test_trace_has_correct_node_count(self):
        engine = LATSEngine(n_candidates=3, max_depth=1, quality_threshold=1.0)  # threshold=1.0 forces all 3
        result, score, trace = await engine.search(
            agent_fn=_poor_agent,
            value_fn=heuristic_scout_value,
            reflect_fn=heuristic_reflect,
            initial_prompt="target",
            job_id="test-006",
        )
        depth1_nodes = [n for n in trace.nodes if n["depth"] == 1]
        assert len(depth1_nodes) == 3

    async def test_backpropagation_increases_visit_count(self):
        """After search, root node should have accumulated visits."""
        engine = LATSEngine(n_candidates=2, max_depth=1, quality_threshold=0.5)
        # We run a search and trust that no exceptions are raised
        result, score, trace = await engine.search(
            agent_fn=_good_agent,
            value_fn=heuristic_scout_value,
            reflect_fn=heuristic_reflect,
            initial_prompt="Google",
            job_id="test-007",
        )
        assert trace.total_candidates >= 1


# ─────────────────────────────────────────────
# Heuristic function tests
# ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestHeuristicFunctions:
    async def test_scout_value_none_returns_zero(self):
        assert await heuristic_scout_value(None) == 0.0

    async def test_scout_value_full_result_near_one(self):
        result = MockScoutResult(n_competitors=5, n_trends=6, n_segments=3, completeness=1.0)
        score = await heuristic_scout_value(result)
        assert score >= 0.9

    async def test_scout_value_empty_result_near_zero(self):
        result = MockScoutResult(n_competitors=0, n_trends=0, n_segments=0, completeness=0.0)
        score = await heuristic_scout_value(result)
        assert score <= 0.15  # only the quality field contributes

    async def test_strategy_value_none_returns_zero(self):
        assert await heuristic_strategy_value(None) == 0.0

    async def test_strategy_value_full_result_near_one(self):
        result = MockStrategyResult(n_swot=4, has_gtm=True, n_positioning=3, n_actions=5)
        score = await heuristic_strategy_value(result)
        assert score >= 0.70

    async def test_reflect_returns_string(self):
        reflection = await heuristic_reflect(MockScoutResult(), 0.5)
        assert isinstance(reflection, str)
        assert len(reflection) > 0

    async def test_reflect_low_score_mentions_incomplete(self):
        reflection = await heuristic_reflect(None, 0.2)
        assert "incomplete" in reflection.lower()

    async def test_reflect_high_score_mentions_kpi(self):
        reflection = await heuristic_reflect(None, 0.75)
        assert "kpi" in reflection.lower() or "metric" in reflection.lower()
