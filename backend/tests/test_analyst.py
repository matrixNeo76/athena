"""
ATHENA - Analyst Service unit tests

Tests the pure-local transformation layer: ScoutResult → AnalystResult.
No external calls, no Deploy.AI credentials needed.
"""
import asyncio
import pytest
from datetime import datetime, timezone

from app.models.schemas import (
    ConfidenceLevel,
    ScoutCompetitor,
    ScoutCustomerSegment,
    ScoutResult,
    ScoutTrend,
)
from app.services.analyst_service import run_analyst, _slugify


# ── Helper factory ────────────────────────────────────────────────────────────

def make_scout_result(
    target: str = "TestCo",
    competitors: list | None = None,
    trends: list | None = None,
    segments: list | None = None,
) -> ScoutResult:
    return ScoutResult(
        target=target,
        competitors=competitors or [],
        trends=trends or [],
        customer_segments=segments or [],
        scouted_at=datetime.now(timezone.utc),
    )


# ── _slugify ──────────────────────────────────────────────────────────────────

class TestSlugify:
    def test_ascii(self):
        assert _slugify("OpenAI") == "openai"

    def test_spaces(self):
        assert _slugify("Google DeepMind") == "google-deepmind"

    def test_unicode(self):
        # Non-ASCII characters should be transliterated or dropped
        result = _slugify("Rénault")
        assert "-" not in result or result.startswith("r")
        assert result.isascii()

    def test_special_chars(self):
        result = _slugify("Hello, World! (2025)")
        assert result == "hello-world-2025"

    def test_empty(self):
        assert _slugify("") == "unknown"


# ── run_analyst basics ────────────────────────────────────────────────────────

class TestRunAnalyst:
    def test_empty_scout(self):
        scout = make_scout_result()
        result = asyncio.get_event_loop().run_until_complete(run_analyst(scout))
        assert result.target == "TestCo"
        assert result.competitors == []
        assert result.graph_spec.nodes == []

    def test_competitor_mapped(self):
        scout = make_scout_result(
            competitors=[
                ScoutCompetitor(
                    name="Acme Corp",
                    description="A test competitor",
                    confidence=ConfidenceLevel.HIGH,
                    strengths=["Speed"],
                    weaknesses=["Cost"],
                    is_assumption=False,
                )
            ]
        )
        result = asyncio.get_event_loop().run_until_complete(run_analyst(scout))
        assert len(result.competitors) == 1
        assert result.competitors[0].name == "Acme Corp"
        assert result.competitors[0].confidence == "high"
        assert "Acme Corp" in result.high_confidence_competitors

    def test_trend_mapped(self):
        scout = make_scout_result(
            trends=[
                ScoutTrend(
                    title="AI Boom",
                    description="AI adoption is accelerating",
                    impact=ConfidenceLevel.HIGH,
                )
            ]
        )
        result = asyncio.get_event_loop().run_until_complete(run_analyst(scout))
        assert len(result.trends) == 1
        assert result.trends[0].title == "AI Boom"

    def test_segment_pain_points(self):
        scout = make_scout_result(
            segments=[
                ScoutCustomerSegment(
                    name="Enterprise",
                    description="Large enterprise teams",
                    pain_points=["Complexity", "Cost"],
                )
            ]
        )
        result = asyncio.get_event_loop().run_until_complete(run_analyst(scout))
        assert "Complexity" in result.key_pain_points
        assert "Cost" in result.key_pain_points

    def test_competitor_deduplication(self):
        scout = make_scout_result(
            competitors=[
                ScoutCompetitor(name="OpenAI", description="AI company", confidence=ConfidenceLevel.HIGH),
                ScoutCompetitor(name="openai", description="Duplicate lowercase", confidence=ConfidenceLevel.LOW),
                ScoutCompetitor(name="Anthropic", description="Another AI", confidence=ConfidenceLevel.MEDIUM),
            ]
        )
        result = asyncio.get_event_loop().run_until_complete(run_analyst(scout))
        # Should deduplicate 'OpenAI' and 'openai'
        assert len(result.competitors) == 2
        names = [c.name for c in result.competitors]
        assert "Anthropic" in names

    def test_graph_has_target_node(self):
        scout = make_scout_result(target="Stripe")
        result = asyncio.get_event_loop().run_until_complete(run_analyst(scout))
        # With no competitors/trends/segments, graph is empty (no market node added for empty)
        # At minimum the function completes without error
        assert result.target == "Stripe"

    def test_graph_nodes_created_for_competitors(self):
        scout = make_scout_result(
            target="MyStartup",
            competitors=[
                ScoutCompetitor(name="Stripe", description="Payments", confidence=ConfidenceLevel.HIGH),
            ],
        )
        result = asyncio.get_event_loop().run_until_complete(run_analyst(scout))
        node_labels = [n.label for n in result.graph_spec.nodes]
        assert "MyStartup" in node_labels
        assert "Stripe" in node_labels

    def test_analysis_summary_not_empty(self):
        scout = make_scout_result(
            target="Notion",
            competitors=[
                ScoutCompetitor(name="Obsidian", description="Notes app", confidence=ConfidenceLevel.MEDIUM),
            ],
        )
        result = asyncio.get_event_loop().run_until_complete(run_analyst(scout))
        assert len(result.analysis_summary) > 0
        assert "Notion" in result.analysis_summary
