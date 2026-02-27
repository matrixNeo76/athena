"""
LATS (Language Agent Tree Search) Engine for ATHENA
=====================================================
Implements Monte Carlo Tree Search-inspired reasoning for LLM agent pipelines.
Each agent call produces candidate outputs that are scored by a value function.
Low-quality outputs trigger reflection + retry (backtracking).

References:
    Zhou et al. (2023) "Language Agent Tree Search Unifies Reasoning,
    Acting, and Planning in Language Models"
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────

@dataclass
class TreeNode:
    """A single node in the LATS search tree."""

    state: Any                                # Agent output stored at this node
    parent: Optional["TreeNode"] = field(default=None, repr=False)
    children: list["TreeNode"] = field(default_factory=list, repr=False)

    # MCTS statistics
    visits: int = 0
    value: float = 0.0          # Accumulated scores (for UCB1 numerator)

    # Quality metadata
    score: float = 0.0          # Direct quality score in [0, 1]
    reflection: str = ""        # Self-critique text from reflect_fn
    depth: int = 0
    is_terminal: bool = False
    created_at: float = field(default_factory=time.time)

    def ucb1(self, exploration_weight: float = 1.414) -> float:
        """Upper Confidence Bound 1 for tree node selection."""
        if self.visits == 0:
            return float("inf")
        parent_visits = self.parent.visits if self.parent else self.visits
        if parent_visits == 0:
            return float("inf")
        exploit = self.value / self.visits
        explore = exploration_weight * math.sqrt(math.log(parent_visits) / self.visits)
        return exploit + explore

    @property
    def is_promising(self) -> bool:
        """True if this node's score meets the quality threshold (0.65)."""
        return self.score >= 0.65


@dataclass
class SearchTrace:
    """Detailed audit trail of the LATS search process."""

    job_id: str
    total_candidates: int = 0
    best_score: float = 0.0
    reflection_triggered: bool = False
    nodes: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0

    def add_node(self, depth: int, candidate_idx: int, score: float, **kwargs) -> None:
        self.nodes.append({
            "depth": depth,
            "candidate": candidate_idx,
            "score": round(score, 4),
            **kwargs,
        })
        self.total_candidates += 1
        if score > self.best_score:
            self.best_score = score

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "total_candidates": self.total_candidates,
            "best_score": round(self.best_score, 4),
            "reflection_triggered": self.reflection_triggered,
            "duration_ms": round(self.duration_ms, 2),
            "nodes": self.nodes,
        }


# ─────────────────────────────────────────────
# LATS Engine
# ─────────────────────────────────────────────

class LATSEngine:
    """
    Language Agent Tree Search engine.

    Usage::

        engine = LATSEngine(n_candidates=3, quality_threshold=0.65)
        result, score, trace = await engine.search(
            agent_fn=my_agent_coroutine,
            value_fn=my_scoring_coroutine,
            reflect_fn=my_reflection_coroutine,
            initial_prompt="...",
            job_id="abc123",
        )

    Args:
        n_candidates:       Number of parallel candidates to generate per level.
        max_depth:          Maximum tree depth (number of reflection iterations).
        quality_threshold:  Score above which early exit triggers (0-1).
        exploration_weight: UCB1 exploration constant (sqrt(2) by default).
        concurrent_expand:  If True, generate candidates concurrently.
    """

    def __init__(
        self,
        n_candidates: int = 3,
        max_depth: int = 2,
        quality_threshold: float = 0.65,
        exploration_weight: float = 1.414,
        concurrent_expand: bool = True,
    ) -> None:
        self.n_candidates = n_candidates
        self.max_depth = max_depth
        self.quality_threshold = quality_threshold
        self.exploration_weight = exploration_weight
        self.concurrent_expand = concurrent_expand

    # ── Public API ────────────────────────────

    async def search(
        self,
        agent_fn: Callable[..., Awaitable[Any]],
        value_fn: Callable[..., Awaitable[float]],
        reflect_fn: Callable[..., Awaitable[str]],
        initial_prompt: str,
        job_id: str = "",
    ) -> tuple[Any, float, SearchTrace]:
        """
        Execute the LATS search loop.

        Returns:
            (best_result, best_score, trace)
        """
        t_start = time.perf_counter()
        trace = SearchTrace(job_id=job_id)
        root = TreeNode(state=None, depth=0)
        best_node: Optional[TreeNode] = None

        logger.info(
            "[LATS][%s] search started | candidates=%d depth=%d threshold=%.2f",
            job_id, self.n_candidates, self.max_depth, self.quality_threshold,
        )

        # ── Depth 1: initial expansion ─────────
        results = await self._expand(agent_fn, initial_prompt, self.n_candidates)

        for idx, result in enumerate(results):
            score = await self._safe_score(value_fn, result)
            node = TreeNode(
                state=result, parent=root, depth=1,
                score=score, visits=1, value=score,
            )
            root.children.append(node)

            trace.add_node(1, idx + 1, score, early_exit=score >= self.quality_threshold)
            logger.debug("[LATS][%s] depth=1 candidate=%d score=%.3f", job_id, idx + 1, score)

            if best_node is None or score > best_node.score:
                best_node = node

            # Early exit: quality threshold reached
            if score >= self.quality_threshold:
                logger.info("[LATS][%s] early exit at depth=1 score=%.3f", job_id, score)
                self._backpropagate(node, score)
                trace.duration_ms = (time.perf_counter() - t_start) * 1000
                return result, score, trace

        # ── Deeper levels: reflection loop ─────
        for depth in range(2, self.max_depth + 1):
            if best_node is None:
                break

            reflection = await self._safe_reflect(reflect_fn, best_node.state, best_node.score)
            best_node.reflection = reflection
            trace.reflection_triggered = True

            logger.info(
                "[LATS][%s] depth=%d reflection triggered | prev_score=%.3f",
                job_id, depth, best_node.score,
            )

            improved_prompt = self._build_improved_prompt(initial_prompt, reflection)
            refined = await self._expand(
                agent_fn, improved_prompt, max(2, self.n_candidates - 1)
            )

            for idx, result in enumerate(refined):
                score = await self._safe_score(value_fn, result)
                node = TreeNode(
                    state=result, parent=best_node, depth=depth,
                    score=score, visits=1, value=score,
                )
                best_node.children.append(node)

                trace.add_node(depth, idx + 1, score, reflection_applied=True)
                logger.debug(
                    "[LATS][%s] depth=%d candidate=%d score=%.3f",
                    job_id, depth, idx + 1, score,
                )

                if score > best_node.score:
                    best_node = node

                if score >= self.quality_threshold:
                    self._backpropagate(node, score)
                    trace.duration_ms = (time.perf_counter() - t_start) * 1000
                    return result, score, trace

        # ── Return best found ──────────────────
        final_result = best_node.state if best_node else None
        final_score = best_node.score if best_node else 0.0
        if best_node:
            self._backpropagate(best_node, final_score)

        trace.duration_ms = (time.perf_counter() - t_start) * 1000
        logger.info(
            "[LATS][%s] search complete | best_score=%.3f nodes=%d reflection=%s duration=%.0fms",
            job_id, final_score, trace.total_candidates,
            trace.reflection_triggered, trace.duration_ms,
        )
        return final_result, final_score, trace

    # ── Private helpers ───────────────────────

    async def _expand(
        self,
        agent_fn: Callable,
        prompt: str,
        n: int,
    ) -> list[Any]:
        """Generate n candidates, optionally concurrently."""
        if self.concurrent_expand:
            tasks = [self._safe_call(agent_fn, prompt) for _ in range(n)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
            for _ in range(n):
                results.append(await self._safe_call(agent_fn, prompt))
        return [r for r in results if r is not None and not isinstance(r, Exception)]

    @staticmethod
    async def _safe_call(fn: Callable, *args) -> Optional[Any]:
        """Call an async function safely, returning None on error."""
        try:
            return await fn(*args)
        except Exception as exc:
            logger.warning("[LATS] agent_fn error: %s", exc)
            return None

    @staticmethod
    async def _safe_score(value_fn: Callable, result: Any) -> float:
        """Score a result, returning 0.5 (neutral) on failure."""
        try:
            score = await value_fn(result)
            return float(max(0.0, min(1.0, score)))
        except Exception as exc:
            logger.warning("[LATS] value_fn error: %s", exc)
            return 0.5

    @staticmethod
    async def _safe_reflect(reflect_fn: Callable, result: Any, score: float) -> str:
        """Generate reflection text, returning a generic fallback on failure."""
        try:
            return await reflect_fn(result, score)
        except Exception as exc:
            logger.warning("[LATS] reflect_fn error: %s", exc)
            return "Improve comprehensiveness and accuracy of the analysis."

    @staticmethod
    def _build_improved_prompt(original_prompt: str, reflection: str) -> str:
        """Augment the original prompt with reflection feedback."""
        return (
            f"{original_prompt}\n\n"
            "---\n"
            "## Quality Feedback from previous attempt:\n"
            f"{reflection}\n\n"
            "Please address the above feedback to produce a higher-quality analysis."
        )

    @staticmethod
    def _backpropagate(node: TreeNode, value: float) -> None:
        """Propagate value scores up the tree from leaf to root."""
        current: Optional[TreeNode] = node
        while current is not None:
            current.visits += 1
            current.value += value
            current = current.parent


# ─────────────────────────────────────────────
# Heuristic value / reflect functions
# Used as defaults when no custom ones are provided
# ─────────────────────────────────────────────

async def heuristic_scout_value(result: Any) -> float:
    """
    Heuristic scoring for ScoutResult.
    Checks completeness: competitor count, trends, segments, data quality.
    Returns a value in [0, 1].
    """
    if result is None:
        return 0.0
    score = 0.0
    try:
        competitors = getattr(result, "competitors", []) or []
        trends = getattr(result, "market_trends", []) or []
        segments = getattr(result, "customer_segments", []) or []

        # Up to 0.35 for competitors (5+ = full score)
        score += min(0.35, len(competitors) * 0.07)
        # Up to 0.30 for trends
        score += min(0.30, len(trends) * 0.06)
        # Up to 0.20 for segments
        score += min(0.20, len(segments) * 0.10)
        # Up to 0.15 for data quality field
        dq = getattr(result, "data_quality", {}) or {}
        completeness = dq.get("completeness_score", 0.5) if isinstance(dq, dict) else 0.5
        score += 0.15 * float(completeness)
    except Exception:
        score = 0.5
    return min(1.0, score)


async def heuristic_strategy_value(result: Any) -> float:
    """
    Heuristic scoring for StrategyResult.
    Checks SWOT completeness, GTM presence, positioning options.
    Returns a value in [0, 1].
    """
    if result is None:
        return 0.0
    score = 0.0
    try:
        swot = getattr(result, "swot", None)
        if swot:
            s = len(getattr(swot, "strengths", []) or [])
            w = len(getattr(swot, "weaknesses", []) or [])
            o = len(getattr(swot, "opportunities", []) or [])
            t = len(getattr(swot, "threats", []) or [])
            # Up to 0.40 for SWOT (4 quadrants x 4 items each = ideal)
            score += min(0.40, (s + w + o + t) * 0.025)
        if getattr(result, "gtm", None):
            score += 0.25
        positioning = getattr(result, "positioning_options", []) or []
        score += min(0.20, len(positioning) * 0.067)
        actions = getattr(result, "immediate_actions", []) or []
        score += min(0.15, len(actions) * 0.05)
    except Exception:
        score = 0.5
    return min(1.0, score)


async def heuristic_reflect(result: Any, score: float) -> str:
    """
    Generates a reflection prompt based on score severity.
    In production this can call a critic LLM for detailed feedback.
    """
    lines = [f"The analysis scored {score:.2f}/1.00. Specific improvements needed:"]
    if score < 0.40:
        lines += [
            "- The output is significantly incomplete. Ensure all required sections are populated.",
            "- Provide at least 5 competitors with detailed profiles and confidence scores.",
            "- Include minimum 4 market trends with supporting evidence and URLs.",
            "- Add at least 3 customer segments with pain points and personas.",
        ]
    elif score < 0.65:
        lines += [
            "- Add more specific data points with source attribution for each claim.",
            "- Strengthen the SWOT analysis with concrete, evidence-backed examples.",
            "- Expand the GTM strategy with clear timelines and success metrics.",
            "- Add quantitative estimates (market size, growth rate, percentages).",
        ]
    else:
        lines += [
            "- Add quantitative metrics (market sizes, growth rates, funding data).",
            "- Include more specific competitive differentiation analysis with examples.",
            "- Strengthen success metrics with measurable, time-bound KPIs.",
            "- Add contingency strategies for the top 2 identified risks.",
        ]
    return "\n".join(lines)
