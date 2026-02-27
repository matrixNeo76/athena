"""
ATHENA - Full stub pipeline integration tests

Runs the complete Scout → Analyst → Strategy → Presenter pipeline in stub
mode, verifying end-to-end data flow without any external API calls or
Deploy.AI credentials.

These tests are the closest approximation to a live hackathon demo in CI.
Stub mode is forced via a module-scoped fixture that patches is_stub_mode
on the Settings class, ensuring tests pass regardless of any .env file.
"""
import asyncio
from datetime import datetime, timezone

import pytest

from app.models.schemas import PipelineStage
from app.services.scout_agent import run_scout
from app.services.analyst_service import run_analyst
from app.services.strategy_agent import run_strategy
from app.services.presenter_service import run_presenter


# ── Force stub mode for all tests in this module ─────────────────────────────

@pytest.fixture(autouse=True)
def force_stub_mode(monkeypatch):
    """
    Patch is_stub_mode on the Settings class so it always returns True
    regardless of .env file contents.  This guarantees stub mode in CI
    and in developer environments with real credentials configured.
    """
    from app.core.config import Settings
    monkeypatch.setattr(Settings, "is_stub_mode", property(lambda self: True))


# ── Scout stage ───────────────────────────────────────────────────────────────

class TestStubScout:
    def test_returns_scout_result_with_correct_target(self):
        result = asyncio.run(run_scout("OpenAI"))
        assert result.target == "OpenAI"

    def test_has_at_least_3_competitors(self):
        result = asyncio.run(run_scout("TestTarget"))
        assert len(result.competitors) >= 3, (
            f"Expected ≥3 stub competitors, got {len(result.competitors)}"
        )

    def test_has_at_least_3_trends(self):
        result = asyncio.run(run_scout("TestTarget"))
        assert len(result.trends) >= 3

    def test_has_at_least_2_customer_segments(self):
        result = asyncio.run(run_scout("TestTarget"))
        assert len(result.customer_segments) >= 2

    def test_scouted_at_is_set(self):
        result = asyncio.run(run_scout("TestTarget"))
        assert result.scouted_at is not None

    def test_data_quality_is_present(self):
        result = asyncio.run(run_scout("TestTarget"))
        assert result.data_quality is not None
        assert result.data_quality.coverage_score >= 0

    def test_all_competitors_have_name_and_description(self):
        result = asyncio.run(run_scout("TestTarget"))
        for c in result.competitors:
            assert c.name and len(c.name) > 0
            assert c.description and len(c.description) > 0


# ── Scout → Analyst ───────────────────────────────────────────────────────────

class TestStubAnalyst:
    def test_scout_to_analyst_preserves_target(self):
        scout = asyncio.run(run_scout("Stripe"))
        analyst = asyncio.run(run_analyst(scout))
        assert analyst.target == "Stripe"

    def test_analyst_has_competitors(self):
        scout = asyncio.run(run_scout("Stripe"))
        analyst = asyncio.run(run_analyst(scout))
        assert len(analyst.competitors) > 0

    def test_graph_has_nodes_and_edges(self):
        scout = asyncio.run(run_scout("Notion"))
        analyst = asyncio.run(run_analyst(scout))
        assert len(analyst.graph_spec.nodes) > 0
        assert len(analyst.graph_spec.edges) > 0

    def test_graph_contains_target_node(self):
        target = "Figma"
        scout = asyncio.run(run_scout(target))
        analyst = asyncio.run(run_analyst(scout))
        node_labels = [n.label for n in analyst.graph_spec.nodes]
        assert target in node_labels, f"Target node '{target}' missing from graph"

    def test_analysis_summary_mentions_target(self):
        scout = asyncio.run(run_scout("Canva"))
        analyst = asyncio.run(run_analyst(scout))
        assert "Canva" in analyst.analysis_summary

    def test_analyzed_at_is_set(self):
        scout = asyncio.run(run_scout("TestTarget"))
        analyst = asyncio.run(run_analyst(scout))
        assert analyst.analyzed_at is not None


# ── Scout → Analyst → Strategy ───────────────────────────────────────────────

class TestStubStrategy:
    def test_pipeline_through_strategy_preserves_target(self):
        scout = asyncio.run(run_scout("Figma"))
        analyst = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        assert strategy.target == "Figma"

    def test_swot_is_present(self):
        scout = asyncio.run(run_scout("TestCo"))
        analyst = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        assert strategy.swot is not None

    def test_swot_has_all_four_quadrants(self):
        scout = asyncio.run(run_scout("TestCo"))
        analyst = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        swot = strategy.swot
        assert len(swot.strengths)     > 0, "SWOT: no strengths"
        assert len(swot.weaknesses)    > 0, "SWOT: no weaknesses"
        assert len(swot.opportunities) > 0, "SWOT: no opportunities"
        assert len(swot.threats)       > 0, "SWOT: no threats"

    def test_has_positioning_options(self):
        scout = asyncio.run(run_scout("TestCo"))
        analyst = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        assert len(strategy.positioning_options) >= 1

    def test_gtm_plan_is_present(self):
        scout = asyncio.run(run_scout("TestCo"))
        analyst = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        assert strategy.gtm_plan is not None

    def test_gtm_value_proposition_not_empty(self):
        scout = asyncio.run(run_scout("TestCo"))
        analyst = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        assert strategy.gtm_plan.value_proposition and len(strategy.gtm_plan.value_proposition) > 10

    def test_strategized_at_is_set(self):
        scout = asyncio.run(run_scout("TestCo"))
        analyst = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        assert strategy.strategized_at is not None


# ── Full end-to-end pipeline (Scout → Analyst → Strategy → Presenter) ─────────

class TestFullStubPipeline:
    def test_full_pipeline_completes_without_error(self, tmp_path, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))

        target   = "Complete AI"
        scout    = asyncio.run(run_scout(target))
        analyst  = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        presenter = asyncio.run(run_presenter("e2e-test-job", strategy, analyst))

        # Scout
        assert scout.target == target
        assert len(scout.competitors) > 0
        # Analyst
        assert len(analyst.competitors) > 0
        assert len(analyst.graph_spec.nodes) > 0
        # Strategy
        assert strategy.swot is not None
        assert len(strategy.positioning_options) >= 1
        # Presenter
        assert len(presenter.report_markdown) > 500
        assert len(presenter.deck_outline) == 8
        assert presenter.report_url == "/api/v1/reports/e2e-test-job.md"
        assert presenter.presented_at is not None

    def test_report_contains_all_8_sections(self, tmp_path, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))

        scout    = asyncio.run(run_scout("Anthropic"))
        analyst  = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        presenter = asyncio.run(run_presenter("sections-e2e", strategy, analyst))

        md = presenter.report_markdown
        expected_sections = [
            "1. Executive Overview",
            "2. Market & Competitors",
            "3. Market Trends",
            "4. Customer Segments",
            "5. Strategic Analysis",
            "6. Positioning Options",
            "7. Go-to-Market Plan",
            "8. Next Steps",
        ]
        for section in expected_sections:
            assert section in md, f"Missing section in e2e report: '{section}'"

    def test_deck_has_8_sequential_slides(self, tmp_path, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))

        scout    = asyncio.run(run_scout("Deploy AI"))
        analyst  = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        presenter = asyncio.run(run_presenter("deck-e2e", strategy, analyst))

        assert len(presenter.deck_outline) == 8
        for i, slide in enumerate(presenter.deck_outline, start=1):
            assert slide.slide_number == i

    def test_e2e_report_file_written_to_disk(self, tmp_path, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))

        scout    = asyncio.run(run_scout("ATHENA"))
        analyst  = asyncio.run(run_analyst(scout))
        strategy = asyncio.run(run_strategy(analyst))
        asyncio.run(run_presenter("disk-e2e-test", strategy, analyst))

        report_file = tmp_path / "disk-e2e-test.md"
        assert report_file.exists(), "E2E report not written to disk"
        content = report_file.read_text(encoding="utf-8")
        assert len(content) > 500
