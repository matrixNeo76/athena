"""
ATHENA - Scout Agent integration
TODO-3 ✓: Calls the Complete.dev Scout Agent and parses SCOUT_JSON_OUTPUT
           into a validated ScoutResult Pydantic model.

STUB MODE: when settings.is_stub_mode is True (no credentials configured),
           returns realistic deterministic demo data so the full pipeline
           can be demonstrated without a live Deploy.AI connection.

FIX: _extract_json() moved to services/utils.py (shared with strategy_agent,
     eliminates code duplication).
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.models.schemas import (
    ConfidenceLevel,
    ScoutCompetitor,
    ScoutCustomerSegment,
    ScoutDataQuality,
    ScoutLink,
    ScoutResult,
    ScoutTrend,
)
from app.services.deploy_ai_client import DeployAIError, call_agent
from app.services.utils import extract_json

logger = logging.getLogger(__name__)


# ── Stub / demo response ─────────────────────────────────────────────────────

def _stub_scout_result(target: str) -> ScoutResult:
    """
    Returns realistic demo data when stub mode is active.
    Allows the full pipeline to run for demos / CI without real API credentials.
    """
    logger.info("[SCOUT] STUB MODE — returning demo data for target='%s'", target)
    return ScoutResult(
        target=target,
        competitors=[
            ScoutCompetitor(
                name="OpenAI",
                description="Leading AI research company providing GPT-4, o1, and API platform services.",
                market_position="Market leader by developer mindshare and API volume",
                strengths=["Broad model portfolio", "Large developer ecosystem", "Strong brand recognition"],
                weaknesses=["High inference cost", "API rate limits", "Privacy and data retention concerns"],
                confidence=ConfidenceLevel.HIGH,
                is_assumption=False,
                source_url="https://openai.com",
            ),
            ScoutCompetitor(
                name="Google DeepMind / Gemini",
                description="Google's AI division with Gemini model family and Vertex AI cloud integration.",
                market_position="Strong challenger with deep Google Cloud and Search integration",
                strengths=["Google-scale infrastructure", "Multi-modal capabilities", "Search data advantage"],
                weaknesses=["Enterprise trust deficit vs. Microsoft", "Complex product naming"],
                confidence=ConfidenceLevel.HIGH,
                is_assumption=False,
                source_url="https://deepmind.google",
            ),
            ScoutCompetitor(
                name="Anthropic",
                description="Safety-focused AI company behind the Claude model family.",
                market_position="Premium enterprise AI with safety and long-context leadership",
                strengths=["Constitutional AI safety approach", "Long context windows (200K tokens)", "Strong enterprise contracts"],
                weaknesses=["Smaller ecosystem than OpenAI", "Higher price point", "Limited multimodal support"],
                confidence=ConfidenceLevel.HIGH,
                is_assumption=False,
                source_url="https://anthropic.com",
            ),
            ScoutCompetitor(
                name="Mistral AI",
                description="European open-weight model provider with on-premise deployment options.",
                market_position="Open-source / privacy-first challenger",
                strengths=["Open weights", "European data sovereignty", "Efficient small models"],
                weaknesses=["Smaller R&D budget", "Less enterprise support infrastructure"],
                confidence=ConfidenceLevel.MEDIUM,
                is_assumption=False,
            ),
        ],
        trends=[
            ScoutTrend(
                title="Agentic AI & Autonomous Workflows",
                description="Multi-agent orchestration is becoming the dominant enterprise AI adoption pattern, with companies building autonomous pipelines that chain specialised agents.",
                impact=ConfidenceLevel.HIGH,
                timeframe="2024\u20132026",
                is_assumption=False,
            ),
            ScoutTrend(
                title="LLM Cost Commoditisation",
                description="Inference costs are falling ~10\u00d7 per year driven by hardware improvements and open-source competition, rapidly expanding addressable markets.",
                impact=ConfidenceLevel.HIGH,
                timeframe="Ongoing",
                is_assumption=False,
            ),
            ScoutTrend(
                title="Enterprise AI Governance & Compliance",
                description="EU AI Act and emerging US regulations are driving demand for explainable, auditable, and controllable AI systems.",
                impact=ConfidenceLevel.MEDIUM,
                timeframe="2025\u20132027",
                is_assumption=False,
            ),
            ScoutTrend(
                title="On-Premise & Sovereign AI Deployment",
                description="Regulated industries (finance, healthcare, government) require on-premise or private-cloud model deployment for data residency compliance.",
                impact=ConfidenceLevel.MEDIUM,
                timeframe="2024\u20132026",
                is_assumption=False,
            ),
        ],
        customer_segments=[
            ScoutCustomerSegment(
                name="Enterprise Engineering Teams",
                description="Large enterprise development teams building internal AI tooling, automation, and developer productivity products.",
                pain_points=["Integration complexity with existing systems", "Compliance and data residency requirements", "Cost at scale", "Model versioning and stability"],
                estimated_size="~50,000 companies globally",
                is_assumption=False,
            ),
            ScoutCustomerSegment(
                name="AI-Native Startups",
                description="Startups building differentiated products on top of foundation models, requiring reliable, scalable API access.",
                pain_points=["Vendor lock-in risk", "API reliability and uptime", "Latency for real-time features", "Rate limit constraints"],
                estimated_size="~200,000 globally",
                is_assumption=False,
            ),
            ScoutCustomerSegment(
                name="SMB Automation Seekers",
                description="Small and medium businesses seeking to automate repetitive processes and augment staff with AI copilots.",
                pain_points=["Technical implementation complexity", "Budget constraints", "ROI uncertainty", "Lack of in-house AI expertise"],
                estimated_size="~1.5M businesses",
                is_assumption=True,
            ),
        ],
        links=[
            ScoutLink(url="https://openai.com/api", title="OpenAI API", relevance="Primary competitor API reference"),
            ScoutLink(url="https://cloud.google.com/vertex-ai", title="Google Vertex AI", relevance="Google's enterprise AI platform"),
            ScoutLink(url="https://www.anthropic.com/claude-for-enterprise", title="Claude for Enterprise", relevance="Anthropic enterprise offering"),
        ],
        data_quality=ScoutDataQuality(
            coverage_score=9,
            freshness="2025",
            gaps=["Real-time pricing data", "Private company financials", "Market share percentages"],
        ),
        assumptions=[
            "SMB segment size is estimated from industry analyst reports",
            "Market position labels are qualitative assessments based on public information",
        ],
        scouted_at=datetime.now(timezone.utc),
    )


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_scout_prompt(target: str, focus_questions: Optional[list[str]]) -> str:
    focus_block = ""
    if focus_questions:
        questions = "\n".join(f"  - {q}" for q in focus_questions)
        focus_block = f"\nPrioritise answering these specific questions:\n{questions}\n"

    return f"""You are the Scout Agent for ATHENA, an autonomous competitive intelligence platform.

Your task is to research the following target and return structured intelligence data:
TARGET: {target}
{focus_block}
CRITICAL INSTRUCTIONS:
1. Return ONLY a single valid JSON object. No markdown, no code fences, no explanations.
2. The JSON must strictly follow the SCOUT_JSON_OUTPUT schema below.
3. For every item, set "is_assumption": true if you could not find a real source.
4. Populate "source_url" whenever possible.

SCOUT_JSON_OUTPUT SCHEMA:
{{
  "target": "{target}",
  "competitors": [
    {{
      "name": "string",
      "description": "string",
      "market_position": "string or null",
      "strengths": ["string"],
      "weaknesses": ["string"],
      "source_url": "string or null",
      "confidence": "high | medium | low",
      "is_assumption": false
    }}
  ],
  "trends": [
    {{
      "title": "string",
      "description": "string",
      "impact": "high | medium | low",
      "timeframe": "string or null",
      "source_url": "string or null",
      "is_assumption": false
    }}
  ],
  "customer_segments": [
    {{
      "name": "string",
      "description": "string",
      "pain_points": ["string"],
      "estimated_size": "string or null",
      "is_assumption": false
    }}
  ],
  "links": [{{"url": "string", "title": "string or null", "relevance": "string or null"}}],
  "data_quality": {{
    "coverage_score": 0,
    "freshness": "string or null",
    "gaps": ["string"]
  }},
  "assumptions": ["string"],
  "scouted_at": "ISO 8601 datetime"
}}

Return ONLY the JSON object. Start your response with {{ and end with }}.
"""


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_scout(
    target: str,
    focus_questions: Optional[list[str]] = None,
) -> ScoutResult:
    logger.info("[SCOUT] run_scout started — target='%s'  stub=%s", target, settings.is_stub_mode)

    # Stub mode: return deterministic demo data (no real API calls)
    if settings.is_stub_mode:
        return _stub_scout_result(target)

    prompt = _build_scout_prompt(target, focus_questions)

    try:
        raw_response = await call_agent(
            agent_id=settings.SCOUT_AGENT_ID,
            prompt=prompt,
            timeout=180.0,
        )
    except DeployAIError as exc:
        logger.error("[SCOUT] API call failed: %s", exc)
        raise

    json_str = extract_json(raw_response, context="SCOUT")

    try:
        data: dict = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"[SCOUT] Malformed JSON from agent: {exc}") from exc

    try:
        result = ScoutResult.model_validate(data)
    except Exception as exc:
        raise ValueError(f"[SCOUT] ScoutResult validation failed: {exc}") from exc

    if result.scouted_at is None:
        result = result.model_copy(update={"scouted_at": datetime.now(timezone.utc)})

    logger.info(
        "[SCOUT] complete — %d competitors, %d trends, %d segments",
        len(result.competitors), len(result.trends), len(result.customer_segments),
    )
    return result
