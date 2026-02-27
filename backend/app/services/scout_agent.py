"""
ATHENA - Scout Agent integration
TODO-3: Calls the Complete.dev Scout Agent and parses SCOUT_JSON_OUTPUT
        into a validated ScoutResult Pydantic model.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.models.schemas import ScoutResult
from app.services.deploy_ai_client import call_agent, DeployAIError

logger = logging.getLogger(__name__)


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
  "links": [{{
    "url": "string",
    "title": "string or null",
    "relevance": "string or null"
  }}],
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
    raise ValueError(f"Scout Agent response contains no JSON. First 300 chars: {text[:300]}")


async def run_scout(
    target: str,
    focus_questions: Optional[list[str]] = None,
) -> ScoutResult:
    logger.info("[SCOUT] run_scout started — target='%s'", target)
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

    json_str = _extract_json(raw_response)

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
