"""
ATHENA - Schema validation unit tests

Verifies that all Pydantic models correctly validate realistic payloads,
ensuring the Scout → Analyst → Strategy → Presenter data contract is tight.
"""
import pytest
from datetime import datetime, timezone

from app.models.schemas import (
    AnalysisStartRequest,
    AnalysisStatusResponse,
    AnalysisResultsResponse,
    ConfidenceLevel,
    DeckSlide,
    GTMModel,
    PipelineStage,
    PresenterResult,
    ScoutCompetitor,
    ScoutResult,
    StrategyResult,
    SWOTModel,
    STAGE_PROGRESS,
)


# ── AnalysisStartRequest ──────────────────────────────────────────────────────

class TestAnalysisStartRequest:
    def test_valid_company(self):
        req = AnalysisStartRequest(target="OpenAI", type="company", depth="standard")
        assert req.target == "OpenAI"
        assert req.type == "company"

    def test_valid_market(self):
        req = AnalysisStartRequest(target="DeFi lending", type="market")
        assert req.depth == "standard"   # default

    def test_target_too_short(self):
        with pytest.raises(Exception):
            AnalysisStartRequest(target="X")

    def test_invalid_type(self):
        with pytest.raises(Exception):
            AnalysisStartRequest(target="OpenAI", type="invalid")

    def test_invalid_depth(self):
        with pytest.raises(Exception):
            AnalysisStartRequest(target="OpenAI", depth="ultra")


# ── PipelineStage & STAGE_PROGRESS ───────────────────────────────────────────

class TestPipelineStage:
    def test_all_stages_have_progress(self):
        for stage in PipelineStage:
            assert stage in STAGE_PROGRESS, f"{stage} missing from STAGE_PROGRESS"

    def test_done_is_100(self):
        assert STAGE_PROGRESS[PipelineStage.DONE] == 100

    def test_error_is_negative(self):
        assert STAGE_PROGRESS[PipelineStage.ERROR] < 0

    def test_pending_is_zero(self):
        assert STAGE_PROGRESS[PipelineStage.PENDING] == 0


# ── ScoutResult ───────────────────────────────────────────────────────────────

class TestScoutResult:
    def test_minimal_valid(self):
        result = ScoutResult(target="Stripe")
        assert result.target == "Stripe"
        assert result.competitors == []
        assert result.trends == []
        assert result.assumptions == []

    def test_competitor_confidence_default(self):
        comp = ScoutCompetitor(
            name="Acme",
            description="Test competitor",
        )
        assert comp.confidence == ConfidenceLevel.MEDIUM
        assert comp.is_assumption is False

    def test_full_payload(self):
        payload = {
            "target": "OpenAI",
            "competitors": [
                {
                    "name": "Anthropic",
                    "description": "Safety AI",
                    "confidence": "high",
                    "is_assumption": False,
                    "strengths": ["Safety"],
                    "weaknesses": ["Cost"],
                }
            ],
            "trends": [],
            "customer_segments": [],
            "scouted_at": "2025-01-01T00:00:00Z",
        }
        result = ScoutResult.model_validate(payload)
        assert len(result.competitors) == 1
        assert result.competitors[0].confidence == ConfidenceLevel.HIGH


# ── SWOTModel & GTMModel ──────────────────────────────────────────────────────

class TestSWOTGTM:
    def test_swot_valid(self):
        swot = SWOTModel(
            strengths=["Speed"],
            weaknesses=["Cost"],
            opportunities=["Enterprise"],
            threats=["Competitors"],
        )
        assert len(swot.strengths) == 1

    def test_gtm_valid(self):
        gtm = GTMModel(
            positioning="Market leader",
            target_segments=["SMB"],
            key_channels=["LinkedIn"],
            value_proposition="Fast and cheap",
            recommended_actions=["Launch PLG"],
        )
        assert gtm.positioning == "Market leader"


# ── DeckSlide ─────────────────────────────────────────────────────────────────

class TestDeckSlide:
    def test_valid_slide(self):
        slide = DeckSlide(
            slide_number=1,
            title="Cover",
            bullets=["ATHENA", "Market Intelligence"],
            speaker_note="Introduce the platform.",
        )
        assert slide.slide_number == 1
        assert slide.speaker_note == "Introduce the platform."

    def test_minimal_slide(self):
        slide = DeckSlide(slide_number=2, title="Overview")
        assert slide.bullets == []
        assert slide.speaker_note is None


# ── PresenterResult ───────────────────────────────────────────────────────────

class TestPresenterResult:
    def test_valid(self):
        result = PresenterResult(
            job_id="abc-123",
            target="OpenAI",
            report_markdown="# Report",
            deck_outline=[
                DeckSlide(slide_number=1, title="Cover")
            ],
            report_url="/api/v1/reports/abc-123.md",
            presented_at=datetime.now(timezone.utc),
        )
        assert result.job_id == "abc-123"
        assert len(result.deck_outline) == 1


# ── AnalysisStatusResponse ────────────────────────────────────────────────────

class TestAnalysisStatusResponse:
    def test_running_status(self):
        resp = AnalysisStatusResponse(
            job_id="test-job",
            target="Stripe",
            stage=PipelineStage.SCOUT,
            status="running",
            progress=20,
            message="Scouting...",
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.stage == PipelineStage.SCOUT
        assert resp.progress == 20

    def test_done_status(self):
        now = datetime.now(timezone.utc)
        resp = AnalysisStatusResponse(
            job_id="done-job",
            target="OpenAI",
            stage=PipelineStage.DONE,
            status="done",
            progress=100,
            message="Complete",
            updated_at=now,
            completed_at=now,
        )
        assert resp.progress == 100
        assert resp.status == "done"
