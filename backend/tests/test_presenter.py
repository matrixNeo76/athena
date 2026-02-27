"""
ATHENA - Presenter Service unit tests

Tests _build_report_markdown(), _build_deck_outline(), and run_presenter()
without any Deploy.AI credentials or network I/O.

All disk writes are redirected to pytest's tmp_path fixture.
"""
import asyncio
from datetime import datetime, timezone

import pytest

from app.models.schemas import (
    AnalystCompetitorSummary,
    AnalystResult,
    AnalystSegmentSummary,
    AnalystTrendSummary,
    GraphSpec,
    PositioningOption,
    RiskLevel,
    StrategyGTMPlan,
    StrategyResult,
    SWOTModel,
)
from app.services.presenter_service import (
    _build_deck_outline,
    _build_report_markdown,
    run_presenter,
)


# ── Test data factories ───────────────────────────────────────────────────────

def make_strategy(target: str = "TestCo") -> StrategyResult:
    """Minimal but realistic StrategyResult for testing."""
    return StrategyResult(
        target=target,
        swot=SWOTModel(
            strengths=["Fast deployment", "Strong brand"],
            weaknesses=["Limited scale", "High cost"],
            opportunities=["Growing market", "Enterprise demand"],
            threats=["Big Tech competition", "Regulation"],
        ),
        positioning_options=[
            PositioningOption(
                name="Speed Leader",
                statement=f"{target} is the fastest platform on the market.",
                target_audience="Enterprise SaaS teams",
                key_differentiator="10x faster than alternatives",
                risk_level=RiskLevel.LOW,
                rationale="Clear speed advantage over incumbents.",
            )
        ],
        gtm_plan=StrategyGTMPlan(
            channels=["LinkedIn", "Product Hunt", "Content marketing"],
            messaging_pillars=["Speed", "Simplicity", "Trust"],
            value_proposition="The fastest competitive intelligence platform.",
            launch_phases=[],
        ),
        strategic_summary=f"{target} leads with speed and simplicity in an underserved market.",
        recommended_positioning_index=0,
        strategized_at=datetime.now(timezone.utc),
    )


def make_analyst(target: str = "TestCo") -> AnalystResult:
    """Minimal but realistic AnalystResult for testing."""
    return AnalystResult(
        target=target,
        competitors=[
            AnalystCompetitorSummary(
                name="CompetitorA",
                description="Main rival in the space",
                market_position="Market leader",
                confidence="high",
                is_assumption=False,
                strengths=["Scale", "Brand"],
                weaknesses=["Legacy tech", "Slow support"],
            ),
            AnalystCompetitorSummary(
                name="CompetitorB",
                description="Rising challenger",
                market_position="Challenger",
                confidence="medium",
                is_assumption=False,
            ),
        ],
        trends=[
            AnalystTrendSummary(
                title="AI-Driven Automation",
                description="Businesses are automating workflows with AI agents.",
                impact="high",
                timeframe="2024-2026",
            ),
            AnalystTrendSummary(
                title="Cost Commoditisation",
                description="LLM inference costs are falling rapidly.",
                impact="medium",
            ),
        ],
        segments=[
            AnalystSegmentSummary(
                name="Enterprise Teams",
                description="Large engineering and strategy teams",
                pain_points=["Integration complexity", "Compliance requirements"],
                estimated_size="50,000 companies globally",
            ),
            AnalystSegmentSummary(
                name="AI-Native Startups",
                description="Startups building on foundation models",
                pain_points=["Vendor lock-in risk", "API reliability"],
                estimated_size="200,000 globally",
            ),
        ],
        graph_spec=GraphSpec(),
        analysis_summary=f"{target} competes with CompetitorA and CompetitorB in a fast-growing AI market.",
        high_confidence_competitors=["CompetitorA"],
        key_pain_points=["Integration complexity", "Vendor lock-in risk"],
        analyzed_at=datetime.now(timezone.utc),
    )


# ── _build_report_markdown ────────────────────────────────────────────────────

class TestBuildReportMarkdown:
    def test_has_all_8_sections(self):
        md = _build_report_markdown("job-001", make_strategy(), make_analyst())
        expected = [
            "1. Executive Overview",
            "2. Market & Competitors",
            "3. Market Trends",
            "4. Customer Segments",
            "5. Strategic Analysis",
            "6. Positioning Options",
            "7. Go-to-Market Plan",
            "8. Next Steps",
        ]
        for section in expected:
            assert section in md, f"Section missing from report: '{section}'"

    def test_target_in_title(self):
        md = _build_report_markdown("job-001", make_strategy("Stripe"), make_analyst("Stripe"))
        assert "Stripe" in md

    def test_job_id_in_report(self):
        md = _build_report_markdown("unique-job-xyz", make_strategy(), make_analyst())
        assert "unique-job-xyz" in md

    def test_swot_all_quadrants_present(self):
        md = _build_report_markdown("job-001", make_strategy(), make_analyst())
        for keyword in ["Strengths", "Weaknesses", "Opportunities", "Threats"]:
            assert keyword in md, f"SWOT quadrant missing: {keyword}"

    def test_competitor_in_table(self):
        md = _build_report_markdown("job-001", make_strategy(), make_analyst())
        assert "CompetitorA" in md
        assert "CompetitorB" in md

    def test_customer_segment_present(self):
        md = _build_report_markdown("job-001", make_strategy(), make_analyst())
        assert "Enterprise Teams" in md
        assert "AI-Native Startups" in md

    def test_trend_present(self):
        md = _build_report_markdown("job-001", make_strategy(), make_analyst())
        assert "AI-Driven Automation" in md

    def test_value_proposition_present(self):
        md = _build_report_markdown("job-001", make_strategy(), make_analyst())
        assert "fastest competitive intelligence" in md

    def test_no_analyst_still_generates_all_sections(self):
        """Presenter must not crash when analyst_result=None."""
        md = _build_report_markdown("job-001", make_strategy(), None)
        assert "1. Executive Overview" in md
        assert "8. Next Steps" in md

    def test_report_footer_present(self):
        md = _build_report_markdown("job-001", make_strategy(), make_analyst())
        assert "ATHENA" in md
        assert "Scout" in md


# ── _build_deck_outline ───────────────────────────────────────────────────────

class TestBuildDeckOutline:
    def test_exactly_8_slides(self):
        slides = _build_deck_outline(make_strategy(), make_analyst())
        assert len(slides) == 8

    def test_slide_numbers_sequential_from_1(self):
        slides = _build_deck_outline(make_strategy(), make_analyst())
        for expected_num, slide in enumerate(slides, start=1):
            assert slide.slide_number == expected_num, (
                f"Slide {expected_num} has wrong slide_number={slide.slide_number}"
            )

    def test_cover_slide_contains_target(self):
        slides = _build_deck_outline(make_strategy("Stripe"), make_analyst("Stripe"))
        assert "Stripe" in slides[0].title

    def test_all_slides_have_non_empty_title(self):
        slides = _build_deck_outline(make_strategy(), make_analyst())
        for slide in slides:
            assert slide.title and len(slide.title) > 0

    def test_all_slides_have_bullets_list(self):
        slides = _build_deck_outline(make_strategy(), make_analyst())
        for slide in slides:
            assert isinstance(slide.bullets, list), (
                f"Slide {slide.slide_number} bullets is not a list"
            )

    def test_all_slides_have_speaker_note(self):
        slides = _build_deck_outline(make_strategy(), make_analyst())
        for slide in slides:
            assert slide.speaker_note is not None and len(slide.speaker_note) > 0, (
                f"Slide {slide.slide_number} missing speaker_note"
            )

    def test_swot_slide_has_quadrant_bullets(self):
        """Slide 6 should reference SWOT items."""
        slides = _build_deck_outline(make_strategy(), make_analyst())
        swot_slide = next(s for s in slides if s.slide_number == 6)
        assert len(swot_slide.bullets) >= 4  # S, W, O, T at minimum

    def test_no_analyst_deck_still_has_8_slides(self):
        """Deck must not crash when analyst_result=None."""
        slides = _build_deck_outline(make_strategy(), None)
        assert len(slides) == 8


# ── run_presenter (integration) ───────────────────────────────────────────────

class TestRunPresenter:
    def test_full_run_returns_complete_result(self, tmp_path, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))
        result = asyncio.run(
            run_presenter("job-test-001", make_strategy("OpenAI"), make_analyst("OpenAI"))
        )
        assert result.job_id == "job-test-001"
        assert result.target == "OpenAI"
        assert len(result.report_markdown) > 200
        assert len(result.deck_outline) == 8
        assert result.report_url == "/api/v1/reports/job-test-001.md"
        assert result.presented_at is not None

    def test_report_written_to_disk(self, tmp_path, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))
        asyncio.run(run_presenter("disk-write-test", make_strategy(), make_analyst()))
        report_file = tmp_path / "disk-write-test.md"
        assert report_file.exists(), "Report file was not written to disk"
        content = report_file.read_text(encoding="utf-8")
        assert len(content) > 100

    def test_disk_ioerror_is_nonfatal(self, monkeypatch):
        """OSError on disk write must NOT crash the presenter — report is still returned."""
        from app.core.config import settings
        monkeypatch.setattr(settings, "REPORTS_DIR", "/nonexistent/path/__athena_test__")
        result = asyncio.run(run_presenter("io-err-test", make_strategy(), make_analyst()))
        # Even if disk write fails, report_markdown must be populated
        assert len(result.report_markdown) > 100
        assert len(result.deck_outline) == 8
