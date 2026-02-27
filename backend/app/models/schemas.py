""" 
ATHENA - Pydantic schemas for request/response validation
TODO-3: Added ScoutResult model and sub-models (SCOUT_JSON_OUTPUT contract)
TODO-5: Added AnalystResult, GraphNode, GraphEdge, GraphSpec models
TODO-4: Added StrategyResult and nested STRATEGY_JSON_OUTPUT models
TODO-7: Added DeckSlide and PresenterResult models

FIX: PipelineStage enum values renamed to UPPERCASE to match frontend constants.
FIX: SWOTModel / GTMModel moved before StrategyResult (forward-reference bug).
FIX: AnalysisStatusResponse field renames + new fields (message, status, error_message).
FIX: AnalysisResultsResponse now includes presenter_result for frontend display.
FIX: DeckSlide.speaker_notes renamed to speaker_note (matches frontend accessor).
FIX: AnalysisStartRequest now accepts 'type' field sent by the frontend.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class PipelineStage(str, Enum):
    # FIX: values are now UPPERCASE to match frontend stage constants
    PENDING   = "PENDING"
    SCOUT     = "SCOUT"      # Scout Agent: web/news data collection
    ANALYST   = "ANALYST"    # Analyst Service: structure + knowledge graph
    STRATEGY  = "STRATEGY"   # Strategy Agent: SWOT / GTM
    PRESENTER = "PRESENTER"  # Presenter Service: report / pitch deck
    DONE      = "DONE"
    ERROR     = "ERROR"


STAGE_PROGRESS: dict[PipelineStage, int] = {
    PipelineStage.PENDING:   0,
    PipelineStage.SCOUT:     20,
    PipelineStage.ANALYST:   45,
    PipelineStage.STRATEGY:  70,
    PipelineStage.PRESENTER: 90,
    PipelineStage.DONE:      100,
    PipelineStage.ERROR:     -1,
}

STAGE_LABELS: dict[PipelineStage, str] = {
    PipelineStage.PENDING:   "Job queued, waiting to start",
    PipelineStage.SCOUT:     "Scout Agent collecting web/news data\u2026",
    PipelineStage.ANALYST:   "Analyst Service structuring data & building knowledge graph\u2026",
    PipelineStage.STRATEGY:  "Strategy Agent generating SWOT & GTM recommendations\u2026",
    PipelineStage.PRESENTER: "Presenter Service producing report & pitch deck\u2026",
    PipelineStage.DONE:      "Analysis complete \u2014 results ready",
    PipelineStage.ERROR:     "Pipeline failed",
}


# ──────────────────────────────────────────────
# TODO-3: SCOUT_JSON_OUTPUT — Scout Agent output models
# ──────────────────────────────────────────────

class ConfidenceLevel(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class ScoutCompetitor(BaseModel):
    name: str
    description: str
    market_position: Optional[str] = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    is_assumption: bool = Field(default=False)


class ScoutTrend(BaseModel):
    title: str
    description: str
    impact: ConfidenceLevel = ConfidenceLevel.MEDIUM
    timeframe: Optional[str] = None
    source_url: Optional[str] = None
    is_assumption: bool = False


class ScoutCustomerSegment(BaseModel):
    name: str
    description: str
    pain_points: list[str] = Field(default_factory=list)
    estimated_size: Optional[str] = None
    is_assumption: bool = False


class ScoutLink(BaseModel):
    url: str
    title: Optional[str] = None
    relevance: Optional[str] = None


class ScoutDataQuality(BaseModel):
    coverage_score: int = Field(default=0, ge=0, le=10)
    freshness: Optional[str] = None
    gaps: list[str] = Field(default_factory=list)


class ScoutResult(BaseModel):
    target: str
    competitors: list[ScoutCompetitor] = Field(default_factory=list)
    trends: list[ScoutTrend] = Field(default_factory=list)
    customer_segments: list[ScoutCustomerSegment] = Field(default_factory=list)
    links: list[ScoutLink] = Field(default_factory=list)
    data_quality: Optional[ScoutDataQuality] = None
    assumptions: list[str] = Field(default_factory=list)
    scouted_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# TODO-5: ANALYST output models
# ──────────────────────────────────────────────

class GraphNodeType(str, Enum):
    COMPANY          = "company"
    COMPETITOR       = "competitor"
    MARKET           = "market"
    TREND            = "trend"
    CUSTOMER_SEGMENT = "customer_segment"


class GraphNode(BaseModel):
    id: str = Field(..., description="Unique slug, e.g. 'company-openai'")
    label: str
    node_type: GraphNodeType
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    relation: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class GraphSpec(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    description: str = ""


class AnalystCompetitorSummary(BaseModel):
    name: str
    description: str
    market_position: Optional[str] = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    is_assumption: bool = False


class AnalystTrendSummary(BaseModel):
    title: str
    description: str
    impact: str = "medium"
    timeframe: Optional[str] = None
    is_assumption: bool = False


class AnalystSegmentSummary(BaseModel):
    name: str
    description: str
    pain_points: list[str] = Field(default_factory=list)
    estimated_size: Optional[str] = None


class AnalystResult(BaseModel):
    target: str
    competitors: list[AnalystCompetitorSummary] = Field(default_factory=list)
    trends: list[AnalystTrendSummary] = Field(default_factory=list)
    segments: list[AnalystSegmentSummary] = Field(default_factory=list)
    graph_spec: GraphSpec = Field(default_factory=GraphSpec)
    analysis_summary: str = Field(default="")
    high_confidence_competitors: list[str] = Field(default_factory=list)
    key_pain_points: list[str] = Field(default_factory=list)
    analyzed_at: Optional[datetime] = None
    source_scouted_at: Optional[datetime] = Field(default=None)


# ──────────────────────────────────────────────
# SWOT / GTM response models
# FIX: moved UP here (before StrategyResult) to resolve forward-reference NameError.
# ──────────────────────────────────────────────

class SWOTModel(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]


class GTMModel(BaseModel):
    positioning: str
    target_segments: list[str]
    key_channels: list[str]
    value_proposition: str
    recommended_actions: list[str]


# ──────────────────────────────────────────────
# TODO-4: STRATEGY_JSON_OUTPUT — Strategy Agent output models
# ──────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class PositioningOption(BaseModel):
    name: str
    statement: str
    target_audience: str
    key_differentiator: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    rationale: Optional[str] = None


class ICPModel(BaseModel):
    description: str
    company_size: Optional[str] = None
    industry: Optional[str] = None
    geography: Optional[str] = None
    pain_points: list[str] = Field(default_factory=list)
    buying_triggers: list[str] = Field(default_factory=list)


class GTMPhase(BaseModel):
    name: str
    duration: Optional[str] = None
    actions: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)


class StrategyGTMPlan(BaseModel):
    icp: Optional[ICPModel] = None
    channels: list[str] = Field(default_factory=list)
    messaging_pillars: list[str] = Field(default_factory=list)
    value_proposition: Optional[str] = None
    launch_phases: list[GTMPhase] = Field(default_factory=list)
    competitive_moat: Optional[str] = None


class StrategyResult(BaseModel):
    target: str
    swot: Optional[SWOTModel] = None            # SWOTModel now defined above (FIX)
    positioning_options: list[PositioningOption] = Field(default_factory=list)
    gtm_plan: Optional[StrategyGTMPlan] = None
    strategic_summary: str = Field(default="")
    recommended_positioning_index: int = Field(default=0)
    strategized_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# TODO-7: PRESENTER output models
# ──────────────────────────────────────────────

class DeckSlide(BaseModel):
    slide_number: int
    title: str
    subtitle: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)
    # FIX: renamed speaker_notes → speaker_note to match frontend accessor
    speaker_note: Optional[str] = None


class PresenterResult(BaseModel):
    job_id: str
    target: str
    report_markdown: str = Field(default="")
    deck_outline: list[DeckSlide] = Field(default_factory=list)
    report_path: str = Field(default="")
    report_url: str = Field(default="")
    presented_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# TODO-8: Complete.dev Webhook models
# ──────────────────────────────────────────────

class CompleteDevWebhookPayload(BaseModel):
    job_id: Optional[str] = Field(default=None)
    agent_id: Optional[str] = Field(default=None)
    agent_name: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)
    output: Optional[dict[str, Any]] = Field(default=None)
    chat_id: Optional[str] = Field(default=None)
    event_type: Optional[str] = Field(default=None)
    timestamp: Optional[str] = Field(default=None)
    metadata: Optional[dict[str, Any]] = Field(default=None)

    model_config = {"extra": "allow"}


class WebhookEventResponse(BaseModel):
    ok: bool = True
    job_id: Optional[str] = None
    event_type: Optional[str] = None
    recorded: bool = False
    detail: Optional[str] = None


# ──────────────────────────────────────────────
# Request Models
# ──────────────────────────────────────────────

class AnalysisStartRequest(BaseModel):
    target: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Company name, product, or market to analyse",
        examples=["OpenAI", "Tesla EV market", "Notion"],
    )
    # FIX: added 'type' field — frontend sends {"target": "...", "type": "company|product|market"}
    type: Optional[str] = Field(
        default="company",
        pattern="^(company|product|market)$",
        description="Analysis type: company | product | market",
    )
    depth: Optional[str] = Field(
        default="standard",
        pattern="^(quick|standard|deep)$",
        description="Analysis depth: quick | standard | deep",
    )


# ──────────────────────────────────────────────
# Response Models
# ──────────────────────────────────────────────

class AnalysisStartResponse(BaseModel):
    job_id: str
    target: str
    status: str = "pending"
    stage: PipelineStage
    message: str
    created_at: datetime


class AnalysisStatusResponse(BaseModel):
    """
    FIX: Added 'message' (renamed from 'label'), 'status', 'error_message',
    'failed_at_stage', 'started_at', 'completed_at' to match frontend StatusResponse type.
    """
    job_id: str
    target: str
    stage: PipelineStage
    status: str
    progress: int = Field(..., ge=-1, le=100)
    message: str
    error_message: Optional[str] = None
    failed_at_stage: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime


class AnalysisResultsResponse(BaseModel):
    """
    FIX: Added 'presenter_result' so the frontend can display report_markdown
    and deck_outline. Also added 'status' field required by frontend ResultsResponse type.
    """
    job_id: str
    target: str
    stage: PipelineStage
    status: str = "running"
    # FIX: presenter_result — primary payload consumed by the frontend dashboard
    presenter_result: Optional[PresenterResult] = None
    # Legacy aggregated fields
    swot: Optional[SWOTModel] = None
    gtm: Optional[GTMModel] = None
    competitors: Optional[list[str]] = None
    key_trends: Optional[list[str]] = None
    report_url: Optional[str] = None
    completed_at: Optional[datetime] = None
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    components: dict[str, str]
