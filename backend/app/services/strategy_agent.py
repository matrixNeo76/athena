"""
ATHENA - Strategy Agent integration
TODO-4 ✓: Calls the Complete.dev Strategy Agent and parses STRATEGY_JSON_OUTPUT
           into a validated StrategyResult Pydantic model.

STUB MODE: when settings.is_stub_mode is True, returns realistic deterministic
           demo data so the full pipeline can be demonstrated without credentials.

FIX: _extract_json() moved to services/utils.py (eliminates duplication with
     scout_agent.py).
"""
import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.models.schemas import (
    AnalystResult,
    GTMPhase,
    ICPModel,
    PositioningOption,
    RiskLevel,
    StrategyGTMPlan,
    StrategyResult,
    SWOTModel,
)
from app.services.deploy_ai_client import DeployAIError, call_agent
from app.services.utils import extract_json

logger = logging.getLogger(__name__)


# ── Stub / demo response ─────────────────────────────────────────────────────

def _stub_strategy_result(analyst_result: AnalystResult) -> StrategyResult:
    """Returns realistic demo strategy data when stub mode is active."""
    target = analyst_result.target
    logger.info("[STRATEGY] STUB MODE — returning demo data for target='%s'", target)
    return StrategyResult(
        target=target,
        swot=SWOTModel(
            strengths=[
                "Autonomous multi-agent architecture enables end-to-end intelligence gathering without human intervention",
                "Deploy.AI integration provides access to best-in-class foundation models across the pipeline",
                "Real-time streaming pipeline delivers insights faster than traditional consulting engagements",
                "Modular agent design allows independent scaling and hot-swapping of each pipeline stage",
            ],
            weaknesses=[
                "Dependency on third-party AI APIs introduces reliability and cost risks at scale",
                "In-memory job store limits horizontal scalability (PostgreSQL migration in roadmap)",
                "No human-in-the-loop validation — all intelligence is AI-generated and requires user review",
                "Limited to publicly available information; no proprietary data source integrations yet",
            ],
            opportunities=[
                "Growing enterprise demand for AI-native competitive intelligence tools across all industries",
                "Partnership with data providers (Crunchbase, PitchBook) would dramatically improve data quality",
                "White-label SaaS offering for strategy consulting firms and PE/VC portfolio monitoring",
                "Integration with CRM/BI tools (Salesforce, Tableau) as embedded intelligence layer",
            ],
            threats=[
                "Established players (CB Insights, Crayon, Klue) actively pivoting to AI-native workflows",
                "Foundation model providers building competitive intelligence natively into their products",
                "Data privacy regulations (EU AI Act, GDPR) limiting automated data collection at scale",
                "Rapid commoditisation of AI summarisation reducing perceived differentiation over time",
            ],
        ),
        positioning_options=[
            PositioningOption(
                name="Autonomous Intelligence Ops Platform",
                statement=f"{target} is the autonomous competitive intelligence platform that replaces manual research with a multi-agent AI pipeline \u2014 delivering board-ready market intelligence in minutes, not weeks.",
                target_audience="Series B+ SaaS companies and enterprise strategy teams running quarterly competitive reviews",
                key_differentiator="Fully autonomous pipeline from raw data to structured deck \u2014 zero analyst hours required",
                risk_level=RiskLevel.LOW,
                rationale="Positions on speed and automation, which are the highest-value pain points for the target ICP. Differentiation is clear and defensible through the multi-agent architecture.",
            ),
            PositioningOption(
                name="AI Strategy Co-Pilot for Product Teams",
                statement=f"{target} is the AI co-pilot that gives product managers and founders real-time competitive intelligence and GTM recommendations \u2014 powered by the same technology used by top strategy consultants.",
                target_audience="Product managers and founders at AI-native startups building in competitive markets",
                key_differentiator="Actionable GTM output (not just data) \u2014 includes positioning options and phased launch recommendations",
                risk_level=RiskLevel.MEDIUM,
                rationale="Broader TAM but more crowded positioning space. Requires strong product marketing to differentiate from generic AI summarisation tools.",
            ),
            PositioningOption(
                name="Enterprise Competitive Intelligence API",
                statement=f"{target} is the competitive intelligence API that lets enterprise teams embed real-time market analysis directly into their existing strategy workflows and BI dashboards.",
                target_audience="Enterprise digital transformation teams and management consultancies needing scalable intelligence infrastructure",
                key_differentiator="API-first architecture enables embedding intelligence into existing tools without workflow disruption",
                risk_level=RiskLevel.MEDIUM,
                rationale="High ACV potential but longer sales cycles. Requires significant enterprise security and compliance capabilities to win.",
            ),
        ],
        gtm_plan=StrategyGTMPlan(
            icp=ICPModel(
                description="Series B\u2013D SaaS company with a dedicated strategy or product team running quarterly competitive reviews, operating in a market with 5+ identified competitors.",
                company_size="50\u2013500 employees",
                industry="B2B SaaS / Enterprise Software",
                geography="North America & Western Europe (English-speaking markets first)",
                pain_points=[
                    "Competitive analysis takes 2\u20134 weeks and ties up senior analyst time",
                    "Intelligence is stale by the time it reaches decision-makers",
                    "No consistent framework for translating competitive data into actionable strategy",
                ],
                buying_triggers=[
                    "Fundraising round requiring competitive landscape for investor deck",
                    "New competitor entering market requiring rapid strategic response",
                    "Annual strategy planning cycle kicking off",
                    "Hiring a VP Strategy or CPO who wants better intelligence tooling",
                ],
            ),
            channels=[
                "Product-led growth via free tier (1 analysis/month)",
                "Content marketing \u2014 \u2018State of Competitive Intelligence\u2019 annual report",
                "LinkedIn thought leadership targeting VP Strategy and CPO personas",
                "Partnership with startup accelerators and VC firms for portfolio company adoption",
                "Integration marketplace listings (Notion, Salesforce, Slack)",
            ],
            messaging_pillars=[
                "Speed: Board-ready intelligence in minutes vs. weeks of analyst work",
                "Depth: Multi-agent AI researches, analyses, and strategises in one seamless pipeline",
                "Action: Get positioning options and GTM plans, not just raw data",
                "Trust: Every insight is sourced, confidence-rated, and assumption-flagged",
            ],
            value_proposition="ATHENA turns competitive research from a weeks-long consulting engagement into a 10-minute AI pipeline \u2014 giving strategy teams the intelligence they need, when they need it.",
            launch_phases=[
                GTMPhase(
                    name="Phase 1 \u2014 Hackathon Launch & Validation",
                    duration="0\u201330 days",
                    actions=[
                        "Launch on Product Hunt and Hacker News with demo video",
                        "Onboard 20 design partners from VC portfolio companies",
                        "Collect qualitative feedback on report quality and accuracy",
                        "Identify top 3 validated use cases from early user interviews",
                    ],
                    success_metrics=[
                        "500+ signups in first week",
                        "NPS \u2265 40 from design partner cohort",
                        "3+ testimonials from recognisable companies",
                    ],
                ),
                GTMPhase(
                    name="Phase 2 \u2014 Product-Led Growth",
                    duration="30\u201390 days",
                    actions=[
                        "Launch freemium tier (1 free analysis/month, unlimited paid)",
                        "Build Slack and Notion integrations for automated report delivery",
                        "Implement team collaboration features (shared workspaces, comments)",
                        "SEO content targeting \u2018competitive analysis for [industry]\u2019 keywords",
                    ],
                    success_metrics=[
                        "1,000 MAU",
                        "10% free-to-paid conversion rate",
                        "$10K MRR",
                    ],
                ),
                GTMPhase(
                    name="Phase 3 \u2014 Enterprise Expansion",
                    duration="90\u2013180 days",
                    actions=[
                        "Launch enterprise tier with SSO, audit logs, and SLA guarantees",
                        "Hire first enterprise AE targeting Fortune 500 strategy teams",
                        "Complete SOC2 Type I certification",
                        "Partner with 2 strategy consulting firms as resellers",
                    ],
                    success_metrics=[
                        "5 enterprise logos ($2K+ MRR each)",
                        "$50K MRR total",
                        "< 2% monthly churn",
                    ],
                ),
            ],
            competitive_moat=(
                "The combination of the multi-agent pipeline architecture, the proprietary confidence-scoring "
                "and assumption-flagging framework, and the accumulated domain-specific prompt library creates "
                "compounding defensibility. Each analysis improves prompt quality through feedback loops, and "
                "network effects emerge as teams share and compare intelligence across the organisation."
            ),
        ),
        strategic_summary=(
            f"{target} occupies a blue-ocean position in the emerging \u2018Autonomous Intelligence Operations\u2019 "
            f"category, where the primary competitor is the status quo of manual analyst work. "
            f"The recommended go-to-market leads with product-led growth targeting Series B+ SaaS companies, "
            f"leveraging speed-to-insight as the primary value driver before expanding enterprise with a "
            f"consultative sales overlay."
        ),
        recommended_positioning_index=0,
        strategized_at=datetime.now(timezone.utc),
    )


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_strategy_prompt(analyst_result: AnalystResult) -> str:
    target = analyst_result.target

    comp_lines = [
        f"  - {c.name} [{c.confidence}{'*' if c.is_assumption else ''}]: "
        f"strengths={'; '.join(c.strengths[:3]) or 'n/a'} | weaknesses={'; '.join(c.weaknesses[:3]) or 'n/a'}"
        for c in analyst_result.competitors[:8]
    ]
    trend_lines = [
        f"  - [{t.impact.upper()}] {t.title}: {t.description[:120]}"
        for t in analyst_result.trends[:6]
    ]
    seg_lines = [
        f"  - {s.name}: {s.description[:100]} | pain_points={'; '.join(s.pain_points[:3]) or 'n/a'}"
        for s in analyst_result.segments[:5]
    ]
    pain_points_summary = "; ".join(analyst_result.key_pain_points[:6]) or "not available"

    return f"""You are the Strategy Agent for ATHENA.

TARGET: {target}

\u2550\u2550\u2550 ANALYST SUMMARY \u2550\u2550\u2550
{analyst_result.analysis_summary}

\u2550\u2550\u2550 STRUCTURED DATA \u2550\u2550\u2550
COMPETITORS (* = assumption):
{chr(10).join(comp_lines) or '  (none)'}

MARKET TRENDS:
{chr(10).join(trend_lines) or '  (none)'}

CUSTOMER SEGMENTS:
{chr(10).join(seg_lines) or '  (none)'}

KEY PAIN POINTS: {pain_points_summary}

\u2550\u2550\u2550 OUTPUT: STRATEGY_JSON_OUTPUT \u2550\u2550\u2550
Return ONLY a single valid JSON object:
{{
  "target": "{target}",
  "swot": {{
    "strengths": ["..."],
    "weaknesses": ["..."],
    "opportunities": ["..."],
    "threats": ["..."]
  }},
  "positioning_options": [
    {{
      "name": "...",
      "statement": "...",
      "target_audience": "...",
      "key_differentiator": "...",
      "risk_level": "low | medium | high",
      "rationale": "..."
    }}
  ],
  "gtm_plan": {{
    "icp": {{"description": "...", "company_size": "...", "industry": "...", "geography": "...", "pain_points": ["..."], "buying_triggers": ["..."]}},
    "channels": ["..."],
    "messaging_pillars": ["..."],
    "value_proposition": "...",
    "launch_phases": [{{"name": "...", "duration": "...", "actions": ["..."], "success_metrics": ["..."]}}],
    "competitive_moat": "..."
  }},
  "strategic_summary": "2-3 sentence executive summary",
  "recommended_positioning_index": 0,
  "strategized_at": "ISO 8601 datetime"
}}

RULES: Provide 2-3 positioning_options (best first). recommended_positioning_index must be 0.
Start with {{ and end with }}.
"""


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_strategy(analyst_result: AnalystResult) -> StrategyResult:
    logger.info(
        "[STRATEGY] run_strategy started — target='%s'  stub=%s",
        analyst_result.target, settings.is_stub_mode,
    )

    # Stub mode: return deterministic demo data (no real API calls)
    if settings.is_stub_mode:
        return _stub_strategy_result(analyst_result)

    prompt = _build_strategy_prompt(analyst_result)

    try:
        raw_response = await call_agent(
            agent_id=settings.STRATEGY_AGENT_ID,
            prompt=prompt,
            timeout=180.0,
        )
    except DeployAIError as exc:
        logger.error("[STRATEGY] API call failed: %s", exc)
        raise

    json_str = extract_json(raw_response, context="STRATEGY")

    try:
        data: dict = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"[STRATEGY] Malformed JSON from agent: {exc}") from exc

    try:
        result = StrategyResult.model_validate(data)
    except Exception as exc:
        raise ValueError(f"[STRATEGY] StrategyResult validation failed: {exc}") from exc

    if result.strategized_at is None:
        result = result.model_copy(update={"strategized_at": datetime.now(timezone.utc)})

    logger.info(
        "[STRATEGY] complete — %d positioning options, SWOT: %s",
        len(result.positioning_options), "present" if result.swot else "missing",
    )
    return result
