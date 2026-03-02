"""
ATHENA Model Adapter
=====================
Provider-agnostic LLM interface.

Why offer alternatives to Deploy.AI?
--------------------------------------
- Deploy.AI is a hackathon-specific platform with specific agent IDs;
  any production deployment needs a portable LLM layer.
- Direct provider APIs have lower latency, full model selection, and
  no platform lock-in.
- Ollama enables fully local, private, zero-cost inference — ideal for
  development and regulated environments.
- A single adapter interface means the LATS engine and agents never
  need to know which provider is active.

Configured via LLM_PROVIDER environment variable:
    LLM_PROVIDER=deploy_ai   (default, uses Deploy.AI platform)
    LLM_PROVIDER=openai      (requires OPENAI_API_KEY)
    LLM_PROVIDER=anthropic   (requires ANTHROPIC_API_KEY)
    LLM_PROVIDER=ollama      (requires local Ollama: https://ollama.ai)

All adapters use httpx (already a project dependency) — no extra
package installations required.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────
# Base interface
# ─────────────────────────────────────────────

class ModelAdapter(ABC):
    """
    Abstract base for all LLM adapters.

    All adapters expose a single async method: ``call(prompt, system_prompt)``
    returning the raw text completion from the model.
    """

    @abstractmethod
    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Return the model's text response to *prompt*."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        ...


# ─────────────────────────────────────────────
# Deploy.AI adapter (default)
# ─────────────────────────────────────────────

class DeployAIAdapter(ModelAdapter):
    """
    Wraps the existing deploy_ai_client for use via the ModelAdapter interface.
    Agent ID is selected based on the system_prompt content (scout vs strategy).
    """

    @property
    def provider_name(self) -> str:
        return "deploy_ai"

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        from app.services.deploy_ai_client import call_agent
        # Route to Scout or Strategy agent based on system_prompt hint
        agent_id = (
            settings.SCOUT_AGENT_ID
            if system_prompt and "scout" in system_prompt.lower()
            else settings.STRATEGY_AGENT_ID
        )
        return await call_agent(agent_id=agent_id, prompt=prompt)


# ─────────────────────────────────────────────
# OpenAI adapter
# https://platform.openai.com/docs/api-reference/chat
# ─────────────────────────────────────────────

class OpenAIAdapter(ModelAdapter):
    """
    Direct OpenAI API adapter (gpt-4o / gpt-4-turbo / etc.).
    Uses httpx — no openai SDK required.
    Set OPENAI_API_KEY in .env to activate.
    """

    _BASE_URL = "https://api.openai.com/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return f"openai/{settings.OPENAI_MODEL}"

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = client.post(self._BASE_URL, json=payload, headers=headers)
            resp = await resp  # type: ignore[assignment]
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────
# Anthropic Claude adapter
# https://docs.anthropic.com/en/api/messages
# ─────────────────────────────────────────────

class AnthropicAdapter(ModelAdapter):
    """
    Direct Anthropic Claude adapter.
    Uses httpx — no anthropic SDK required.
    Set ANTHROPIC_API_KEY in .env to activate.

    Best models for ATHENA:
        claude-3-5-sonnet-20241022  — best intelligence (default)
        claude-3-haiku-20240307     — fastest / cheapest
    """

    _BASE_URL = "https://api.anthropic.com/v1/messages"

    @property
    def provider_name(self) -> str:
        return f"anthropic/{settings.ANTHROPIC_MODEL}"

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        payload: dict = {
            "model": settings.ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(self._BASE_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return data["content"][0]["text"]


# ─────────────────────────────────────────────
# Ollama adapter (local, open-source, free)
# https://github.com/ollama/ollama/blob/main/docs/api.md
# ─────────────────────────────────────────────

class OllamaAdapter(ModelAdapter):
    """
    Ollama local model adapter.
    Runs open-source models (Llama 3.2, Mistral, Qwen 2.5, DeepSeek-R1)
    entirely on your machine. No API key. No cost. No data leaves your infra.

    Install: https://ollama.ai
    Pull model: ollama pull llama3.2
    Configure: OLLAMA_MODEL=llama3.2 in .env
    """

    @property
    def provider_name(self) -> str:
        return f"ollama/{settings.OLLAMA_MODEL}"

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        async with httpx.AsyncClient(timeout=300.0) as client:  # local can be slow
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["message"]["content"]


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────

_ADAPTER_MAP: dict[str, type[ModelAdapter]] = {
    "deploy_ai":  DeployAIAdapter,
    "openai":     OpenAIAdapter,
    "anthropic":  AnthropicAdapter,
    "ollama":     OllamaAdapter,
}


def get_model_adapter(provider: Optional[str] = None) -> ModelAdapter:
    """
    Return the configured ModelAdapter.

    Falls back to auto-selection when provider='auto':
    1. openai     (if OPENAI_API_KEY set)
    2. anthropic  (if ANTHROPIC_API_KEY set)
    3. deploy_ai  (if DEPLOY_AI_CLIENT_ID set)
    4. ollama     (always available locally)

    Args:
        provider: override LLM_PROVIDER setting.
    """
    selected = (provider or settings.LLM_PROVIDER).lower().strip()

    if selected == "auto":
        selected = _auto_select_provider()

    adapter_cls = _ADAPTER_MAP.get(selected)
    if adapter_cls is None:
        known = list(_ADAPTER_MAP.keys())
        raise ValueError(
            f"Unknown LLM_PROVIDER '{selected}'. "
            f"Valid options: {known}"
        )

    logger.info("[ModelAdapter] Using provider: %s", selected)
    return adapter_cls()


def _auto_select_provider() -> str:
    """Auto-select the best available provider."""
    if settings.has_openai:
        return "openai"
    if settings.has_anthropic:
        return "anthropic"
    if settings.DEPLOY_AI_CLIENT_ID.strip():
        return "deploy_ai"
    return "ollama"
