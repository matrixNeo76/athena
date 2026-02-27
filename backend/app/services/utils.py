"""
ATHENA - Shared service utilities

Currently provides:
  extract_json(raw, context)  — robustly extracts a JSON object from an LLM
                                response that may include code fences or
                                surrounding prose text.

Imported by:
  - services/scout_agent.py
  - services/strategy_agent.py
"""
import re


def extract_json(raw: str, context: str = "") -> str:
    """
    Robustly extracts a JSON object from an LLM response.

    Strategy:
      1. Code fence — agent wrapped JSON in ```json...``` or ``` ... ```
         despite being told not to.
      2. first-{ / last-} span — handles raw JSON and JSON with surrounding
         prose text.

    Args:
        raw:     The raw string returned by the LLM / agent.
        context: Caller label used in the ValueError message (e.g. "SCOUT").

    Returns:
        The extracted JSON string (not yet parsed).

    Raises:
        ValueError: If no JSON object could be located.
    """
    text = raw.strip()

    # 1. Code fence: ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", text)
    if fence_match:
        inner = fence_match.group(1).strip()
        if inner.startswith("{"):
            return inner

    # 2. Locate the outermost JSON object: first { to last }
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    label = f"[{context}] " if context else ""
    raise ValueError(
        f"{label}No JSON object found in agent response. "
        f"First 300 chars: {text[:300]}"
    )
