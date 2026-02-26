"""
ATHENA - Strategy Agent integration
TODO-4: Calls the Complete.dev Strategy Agent and parses STRATEGY_JSON_OUTPUT
        into a validated StrategyResult Pydantic model.
"""
import json
import logging
import re
from datetime import datetime, timezone

from app.core.config import settings
from app.models.schemas import AnalystResult, StrategyResult
from app.services.deploy_ai_client import call_agent, DeployAIError

logger = logging.getLogger(__name__)


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

═══ ANALYST SUMMARY ═══
{analyst_result.analysis_summary}

═══ STRUCTURED DATA ═══
COMPETITORS (* = assumption):
{chr(10).join(comp_lines) or '  (none)'}

MARKET TRENDS:
{chr(10).join(trend_lines) or '  (none)'}

CUSTOMER SEGMENTS:
{chr(10).join(seg_lines) or '  (none)'}

KEY PAIN POINTS: {pain_points_summary}

═══ OUTPUT: STRATEGY_JSON_OUTPUT ═══
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


def _extract_json(raw: str) -> str:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{{.*?\}})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    if text.startswith("{"):
        return text
    brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if brace_match:
        return brace_match.group(1).strip()
    raise ValueError(f"[STRATEGY] No JSON in agent response. First 300 chars: {text[:300]}")


async def run_strategy(analyst_result: AnalystResult) -> StrategyResult:
    logger.info("[STRATEGY] run_strategy started — target='%s'", analyst_result.target)
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

    json_str = _extract_json(raw_response)

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
