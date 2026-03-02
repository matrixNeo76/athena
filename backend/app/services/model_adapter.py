"""
ATHENA Model Adapter
=====================
Provider-agnostic LLM interface.

Supported providers
-------------------
  deploy_ai   – Deploy.AI platform (default, hackathon)
  openai      – OpenAI direct API
  anthropic   – Anthropic Claude direct API
  groq        – Groq LPU inference (ultra-fast, generous free tier)
  openrouter  – OpenRouter unified gateway (300+ models, free tier available)
  ollama      – Local open-source models (free, private)

Switch provider with one env-var — no code changes:
    LLM_PROVIDER=groq
    LLM_PROVIDER=openrouter
    LLM_PROVIDER=auto   # picks best available

All adapters use httpx (already a project dep) — zero extra installs.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────
# Model catalogues (for reference / IDE autocompletion)
# ─────────────────────────────────────────────

# Groq — https://console.groq.com/docs/models
GROQ_MODELS: dict[str, str] = {
    # ── FREE tier ──
    "llama-3.3-70b-versatile":       "Llama 3.3 70B  — best quality on free tier",
    "llama-3.1-8b-instant":          "Llama 3.1 8B   — fastest model on Groq",
    "llama-3.2-11b-vision-preview":  "Llama 3.2 11B  — vision support",
    "mixtral-8x7b-32768":            "Mixtral 8x7B   — long context (32K)",
    "gemma2-9b-it":                  "Gemma 2 9B     — Google's compact model",
    "gemma-7b-it":                   "Gemma 7B       — lightweight, fast",
    # ── Preview / paid ──
    "llama-3.1-70b-versatile":       "Llama 3.1 70B  — high quality",
    "llama-3.2-90b-vision-preview":  "Llama 3.2 90B  — largest vision model",
    "deepseek-r1-distill-llama-70b": "DeepSeek R1 70B — reasoning / chain-of-thought",
    "qwen-2.5-72b":                  "Qwen 2.5 72B   — multilingual, strong reasoning",
}

# OpenRouter — https://openrouter.ai/models
OPENROUTER_MODELS: dict[str, str] = {
    # ── FREE models (suffix :free, rate-limited) ──
    "meta-llama/llama-3.3-70b-instruct:free":  "Llama 3.3 70B  — best free model",
    "meta-llama/llama-3.1-8b-instruct:free":   "Llama 3.1 8B   — fast & free",
    "google/gemma-2-9b-it:free":               "Gemma 2 9B     — Google, free",
    "mistralai/mistral-7b-instruct:free":       "Mistral 7B     — reliable, free",
    "qwen/qwen-2-7b-instruct:free":            "Qwen 2 7B      — multilingual, free",
    "microsoft/phi-3-mini-128k-instruct:free": "Phi-3 Mini     — 128K context, free",
    "nousresearch/hermes-3-llama-3.1-405b:free": "Hermes 3 405B — powerful, free",
    "deepseek/deepseek-r1:free":               "DeepSeek R1    — reasoning, free",
    # ── PAID models (best quality) ──
    "anthropic/claude-3.5-sonnet":             "Claude 3.5 Sonnet  — best overall",
    "anthropic/claude-3-haiku":                "Claude 3 Haiku     — fast, cheap",
    "openai/gpt-4o":                           "GPT-4o             — OpenAI flagship",
    "openai/gpt-4o-mini":                      "GPT-4o Mini        — cheap OpenAI",
    "google/gemini-pro-1.5":                   "Gemini Pro 1.5     — 1M context",
    "google/gemini-flash-1.5":                 "Gemini Flash 1.5   — fast, cheap",
    "meta-llama/llama-3.1-405b-instruct":      "Llama 3.1 405B     — largest open",
    "deepseek/deepseek-chat":                  "DeepSeek V3        — strong & cheap",
    "deepseek/deepseek-r1":                    "DeepSeek R1        — best reasoning",
    "qwen/qwen-2.5-72b-instruct":              "Qwen 2.5 72B       — multilingual",
    "mistralai/mixtral-8x22b-instruct":        "Mixtral 8x22B      — MoE powerhouse",
    "cohere/command-r-plus-08-2024":           "Command R+        — RAG-optimised",
}


# ─────────────────────────────────────────────
# Base interface
# ─────────────────────────────────────────────

class ModelAdapter(ABC):
    """
    Abstract base for all LLM adapters.
    Single async method: ``call(prompt, system_prompt)`` → str.
    """

    @abstractmethod
    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Return the model’s text response to *prompt*."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider/model identifier."""
        ...


# ─────────────────────────────────────────────
# Shared OpenAI-compatible request helper
# ─────────────────────────────────────────────

async def _openai_compatible_call(
    base_url: str,
    model: str,
    prompt: str,
    system_prompt: Optional[str],
    max_tokens: int,
    temperature: float,
    headers: dict,
    timeout: float = 120.0,
) -> str:
    """
    Shared implementation for all OpenAI-compatible endpoints.
    Groq, OpenRouter and OpenAI all use the same /chat/completions schema.
    """
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(base_url, json=payload, headers=headers)
        resp.raise_for_status()

    return resp.json()["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────
# Deploy.AI adapter (default)
# ─────────────────────────────────────────────

class DeployAIAdapter(ModelAdapter):
    """
    Wraps the existing deploy_ai_client.
    Routes to Scout or Strategy agent based on system_prompt hint.
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
        agent_id = (
            settings.SCOUT_AGENT_ID
            if system_prompt and "scout" in system_prompt.lower()
            else settings.STRATEGY_AGENT_ID
        )
        return await call_agent(agent_id=agent_id, prompt=prompt)


# ─────────────────────────────────────────────
# OpenAI adapter
# ─────────────────────────────────────────────

class OpenAIAdapter(ModelAdapter):
    """
    Direct OpenAI API (gpt-4o / gpt-4-turbo / gpt-4o-mini).
    Env: OPENAI_API_KEY, OPENAI_MODEL
    """

    _URL = "https://api.openai.com/v1/chat/completions"

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
        return await _openai_compatible_call(
            base_url=self._URL,
            model=settings.OPENAI_MODEL,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )


# ─────────────────────────────────────────────
# Anthropic Claude adapter
# ─────────────────────────────────────────────

class AnthropicAdapter(ModelAdapter):
    """
    Direct Anthropic Messages API.
    Env: ANTHROPIC_API_KEY, ANTHROPIC_MODEL
    Best models: claude-3-5-sonnet-20241022 (quality) | claude-3-haiku-20240307 (speed)
    """

    _URL = "https://api.anthropic.com/v1/messages"

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
            resp = await client.post(self._URL, json=payload, headers=headers)
            resp.raise_for_status()

        return resp.json()["content"][0]["text"]


# ─────────────────────────────────────────────
# Groq adapter  —  ultra-fast LPU inference
# https://console.groq.com/docs/openai
# ─────────────────────────────────────────────

class GroqAdapter(ModelAdapter):
    """
    Groq LPU inference — fastest available API, generous free tier.

    Env vars:
        GROQ_API_KEY   — from https://console.groq.com/keys
        GROQ_MODEL     — see GROQ_MODELS catalogue above

    Recommended free-tier models for ATHENA:
        llama-3.3-70b-versatile   — best quality, ~300 tok/s
        llama-3.1-8b-instant      — fastest,     ~750 tok/s
        mixtral-8x7b-32768        — long context (32K tokens)
        deepseek-r1-distill-llama-70b — chain-of-thought reasoning

    API is 100% OpenAI-compatible.
    """

    _URL = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return f"groq/{settings.GROQ_MODEL}"

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        return await _openai_compatible_call(
            base_url=self._URL,
            model=settings.GROQ_MODEL,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=60.0,   # Groq is fast, shorter timeout is fine
        )


# ─────────────────────────────────────────────
# OpenRouter adapter  —  300+ models, free tier available
# https://openrouter.ai/docs
# ─────────────────────────────────────────────

class OpenRouterAdapter(ModelAdapter):
    """
    OpenRouter — unified gateway for 300+ models from all major providers.

    Env vars:
        OPENROUTER_API_KEY    — from https://openrouter.ai/keys
        OPENROUTER_MODEL      — see OPENROUTER_MODELS catalogue above
        OPENROUTER_SITE_URL   — optional, shown on openrouter.ai dashboard
        OPENROUTER_SITE_NAME  — optional, shown on openrouter.ai dashboard

    Free models (no cost, rate-limited):
        meta-llama/llama-3.3-70b-instruct:free  — best free model
        deepseek/deepseek-r1:free               — best free reasoning
        google/gemma-2-9b-it:free
        mistralai/mistral-7b-instruct:free
        qwen/qwen-2-7b-instruct:free

    Paid models (top quality):
        anthropic/claude-3.5-sonnet
        openai/gpt-4o
        deepseek/deepseek-chat          — excellent price/quality ratio
        google/gemini-flash-1.5         — fast, cheap, long context

    API is OpenAI-compatible with two extra optional headers.
    """

    _URL = "https://openrouter.ai/api/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return f"openrouter/{settings.OPENROUTER_MODEL}"

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        # Optional headers improve ranking visibility on openrouter.ai
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_SITE_NAME:
            headers["X-Title"] = settings.OPENROUTER_SITE_NAME

        return await _openai_compatible_call(
            base_url=self._URL,
            model=settings.OPENROUTER_MODEL,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            headers=headers,
            timeout=120.0,
        )


# ─────────────────────────────────────────────
# Ollama adapter  —  local, free, private
# ─────────────────────────────────────────────

class OllamaAdapter(ModelAdapter):
    """
    Ollama — run open-source models locally. Zero cost, fully private.

    Install: https://ollama.ai
    Pull:    ollama pull llama3.2

    Env vars:
        OLLAMA_BASE_URL  — default http://localhost:11434
        OLLAMA_MODEL     — any model pulled via `ollama pull`

    Popular models:
        llama3.2        — Meta Llama 3.2 3B (fast on CPU)
        llama3.1:8b     — Meta Llama 3.1 8B
        mistral         — Mistral 7B
        qwen2.5:7b      — Alibaba Qwen 2.5 7B
        deepseek-r1:7b  — DeepSeek R1 reasoning
        gemma2:9b       — Google Gemma 2 9B
        phi3            — Microsoft Phi-3 (tiny, fast)
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
        messages: list[dict] = []
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
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

        return resp.json()["message"]["content"]


# ─────────────────────────────────────────────
# Registry & factory
# ─────────────────────────────────────────────

_ADAPTER_MAP: dict[str, type[ModelAdapter]] = {
    "deploy_ai":   DeployAIAdapter,
    "openai":      OpenAIAdapter,
    "anthropic":   AnthropicAdapter,
    "groq":        GroqAdapter,
    "openrouter":  OpenRouterAdapter,
    "ollama":      OllamaAdapter,
}


def get_model_adapter(provider: Optional[str] = None) -> ModelAdapter:
    """
    Return the configured ModelAdapter instance.

    provider='auto' triggers auto-selection:
        groq        if GROQ_API_KEY set        (fastest)
        openrouter  if OPENROUTER_API_KEY set  (most models)
        openai      if OPENAI_API_KEY set
        anthropic   if ANTHROPIC_API_KEY set
        deploy_ai   if DEPLOY_AI_CLIENT_ID set
        ollama      always available locally
    """
    selected = (provider or settings.LLM_PROVIDER).lower().strip()

    if selected == "auto":
        selected = _auto_select_provider()

    adapter_cls = _ADAPTER_MAP.get(selected)
    if adapter_cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{selected}'. "
            f"Valid: {list(_ADAPTER_MAP)}"
        )

    logger.info("[ModelAdapter] provider=%s", selected)
    return adapter_cls()


def list_models(provider: Optional[str] = None) -> dict[str, str]:
    """
    Return the model catalogue for a provider.

    Args:
        provider: 'groq' | 'openrouter' | None (returns all)
    """
    catalogues: dict[str, dict[str, str]] = {
        "groq":       GROQ_MODELS,
        "openrouter": OPENROUTER_MODELS,
    }
    if provider:
        return catalogues.get(provider.lower(), {})
    combined: dict[str, str] = {}
    for p, models in catalogues.items():
        combined.update({f"{p}/{k}": v for k, v in models.items()})
    return combined


def _auto_select_provider() -> str:
    """Priority: groq > openrouter > openai > anthropic > deploy_ai > ollama."""
    if settings.has_groq:
        return "groq"
    if settings.has_openrouter:
        return "openrouter"
    if settings.has_openai:
        return "openai"
    if settings.has_anthropic:
        return "anthropic"
    if settings.DEPLOY_AI_CLIENT_ID.strip():
        return "deploy_ai"
    return "ollama"
