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
    "llama-3.3-70b-versatile":        "Llama 3.3 70B  — best quality on free tier",
    "llama-3.1-8b-instant":           "Llama 3.1 8B   — fastest model on Groq",
    "llama-3.2-11b-vision-preview":   "Llama 3.2 11B  — vision support",
    "mixtral-8x7b-32768":             "Mixtral 8x7B   — long context (32K)",
    "gemma2-9b-it":                   "Gemma 2 9B     — Google’s compact model",
    "gemma-7b-it":                    "Gemma 7B       — lightweight, fast",
    # ── Preview / paid ──
    "llama-3.1-70b-versatile":        "Llama 3.1 70B  — high quality",
    "llama-3.2-90b-vision-preview":   "Llama 3.2 90B  — largest vision model",
    "deepseek-r1-distill-llama-70b":  "DeepSeek R1 70B — reasoning / chain-of-thought",
    "qwen-2.5-72b":                   "Qwen 2.5 72B   — multilingual, strong reasoning",
}

# OpenRouter — https://openrouter.ai/models
OPENROUTER_MODELS: dict[str, str] = {
    # ── FREE models (suffix :free, rate-limited) ──
    "meta-llama/llama-3.3-70b-instruct:free":    "Llama 3.3 70B  — best free model",
    "meta-llama/llama-3.1-8b-instruct:free":     "Llama 3.1 8B   — fast & free",
    "google/gemma-2-9b-it:free":                 "Gemma 2 9B     — Google, free",
    "mistralai/mistral-7b-instruct:free":        "Mistral 7B     — reliable, free",
    "qwen/qwen-2-7b-instruct:free":              "Qwen 2 7B      — multilingual, free",
    "microsoft/phi-3-mini-128k-instruct:free":   "Phi-3 Mini     — 128K context, free",
    "nousresearch/hermes-3-llama-3.1-405b:free": "Hermes 3 405B  — powerful, free",
    "deepseek/deepseek-r1:free":                 "DeepSeek R1    — reasoning, free",
    # ── PAID models (best quality) ──
    "anthropic/claude-3.5-sonnet":               "Claude 3.5 Sonnet  — best overall",
    "anthropic/claude-3-haiku":                  "Claude 3 Haiku     — fast, cheap",
    "openai/gpt-4o":                             "GPT-4o             — OpenAI flagship",
    "openai/gpt-4o-mini":                        "GPT-4o Mini        — cheap OpenAI",
    "google/gemini-pro-1.5":                     "Gemini Pro 1.5     — 1M context",
    "google/gemini-flash-1.5":                   "Gemini Flash 1.5   — fast, cheap",
    "meta-llama/llama-3.1-405b-instruct":        "Llama 3.1 405B     — largest open",
    "deepseek/deepseek-chat":                    "DeepSeek V3        — strong & cheap",
    "deepseek/deepseek-r1":                      "DeepSeek R1        — best reasoning",
    "qwen/qwen-2.5-72b-instruct":               "Qwen 2.5 72B       — multilingual",
    "mistralai/mixtral-8x22b-instruct":          "Mixtral 8x22B      — MoE powerhouse",
    "cohere/command-r-plus-08-2024":             "Command R+         — RAG-optimised",
}


# ─────────────────────────────────────────────
# Private shared helpers  (no duplication across adapters)
# ─────────────────────────────────────────────

def _build_chat_messages(
    prompt: str,
    system_prompt: Optional[str] = None,
) -> list[dict]:
    """Build an OpenAI-style chat messages list."""
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


def _bearer_headers(api_key: str) -> dict[str, str]:
    """Standard Authorization + Content-Type headers for Bearer-token APIs."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def _http_post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    """Single-responsibility async POST: raises on non-2xx, returns parsed JSON."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
    return resp.json()


async def _openai_compat_call(
    base_url: str,
    model: str,
    api_key: str,
    prompt: str,
    system_prompt: Optional[str],
    max_tokens: int,
    temperature: float,
    timeout: float,
    extra_headers: Optional[dict] = None,
) -> str:
    """
    Shared implementation for all OpenAI-compatible endpoints.
    Groq, OpenRouter and OpenAI all use the same /chat/completions schema.
    """
    headers = _bearer_headers(api_key)
    if extra_headers:
        headers.update(extra_headers)

    payload = {
        "model": model,
        "messages": _build_chat_messages(prompt, system_prompt),
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = await _http_post(base_url, payload, headers, timeout)
    return data["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────
# Base interface
# ─────────────────────────────────────────────

class ModelAdapter(ABC):
    """
    Abstract base for all LLM adapters.
    Single async method: ``call(prompt, system_prompt)`` → str.
    """
    # Subclasses override this to set a provider-appropriate timeout.
    _TIMEOUT: float = 120.0

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
# Concrete adapters
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


class OpenAIAdapter(ModelAdapter):
    """
    Direct OpenAI API (gpt-4o / gpt-4-turbo / gpt-4o-mini).
    Env: OPENAI_API_KEY, OPENAI_MODEL
    """
    _URL     = "https://api.openai.com/v1/chat/completions"
    _TIMEOUT = 120.0

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
        return await _openai_compat_call(
            base_url=self._URL,
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=self._TIMEOUT,
        )


class AnthropicAdapter(ModelAdapter):
    """
    Direct Anthropic Messages API.
    Env: ANTHROPIC_API_KEY, ANTHROPIC_MODEL
    Best models: claude-3-5-sonnet-20241022 (quality) | claude-3-haiku-20240307 (speed)
    Note: different request/response schema from OpenAI — uses _http_post directly.
    """
    _URL     = "https://api.anthropic.com/v1/messages"
    _TIMEOUT = 120.0

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
            "model":      settings.ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "messages":  [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key":         settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        }
        data = await _http_post(self._URL, payload, headers, self._TIMEOUT)
        return data["content"][0]["text"]


class GroqAdapter(ModelAdapter):
    """
    Groq LPU inference — fastest available API, generous free tier.
    Env: GROQ_API_KEY, GROQ_MODEL  (see GROQ_MODELS catalogue)

    Free-tier recommendations:
        llama-3.3-70b-versatile          best quality  (~300 tok/s)
        llama-3.1-8b-instant             fastest       (~750 tok/s)
        mixtral-8x7b-32768               long context  (32K tokens)
        deepseek-r1-distill-llama-70b    chain-of-thought reasoning
    """
    _URL     = "https://api.groq.com/openai/v1/chat/completions"
    _TIMEOUT = 60.0   # Groq is fast; shorter timeout is appropriate

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
        return await _openai_compat_call(
            base_url=self._URL,
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=self._TIMEOUT,
        )


class OpenRouterAdapter(ModelAdapter):
    """
    OpenRouter — unified gateway for 300+ models from all major providers.
    Env: OPENROUTER_API_KEY, OPENROUTER_MODEL  (see OPENROUTER_MODELS catalogue)

    Free models (rate-limited, append :free):
        meta-llama/llama-3.3-70b-instruct:free  best free model
        deepseek/deepseek-r1:free               best free reasoning
        google/gemma-2-9b-it:free
        mistralai/mistral-7b-instruct:free

    Paid models (top quality):
        anthropic/claude-3.5-sonnet
        openai/gpt-4o
        deepseek/deepseek-chat   (excellent price/quality)
        google/gemini-flash-1.5  (fast, cheap, long context)
    """
    _URL     = "https://openrouter.ai/api/v1/chat/completions"
    _TIMEOUT = 120.0

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
        # OpenRouter accepts two optional headers for dashboard visibility
        extra: dict[str, str] = {}
        if settings.OPENROUTER_SITE_URL:
            extra["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_SITE_NAME:
            extra["X-Title"] = settings.OPENROUTER_SITE_NAME

        return await _openai_compat_call(
            base_url=self._URL,
            model=settings.OPENROUTER_MODEL,
            api_key=settings.OPENROUTER_API_KEY,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=self._TIMEOUT,
            extra_headers=extra or None,
        )


class OllamaAdapter(ModelAdapter):
    """
    Ollama — run open-source models locally. Zero cost, fully private.
    Env: OLLAMA_BASE_URL, OLLAMA_MODEL

    Install: https://ollama.ai  |  Pull: ollama pull llama3.2
    Popular models: llama3.2 | llama3.1:8b | mistral | qwen2.5:7b |
                    deepseek-r1:7b | gemma2:9b | phi3
    Note: different response schema from OpenAI — uses _http_post directly.
    """
    _TIMEOUT = 300.0  # Local inference can be slow on CPU

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
        payload = {
            "model":    settings.OLLAMA_MODEL,
            "messages": _build_chat_messages(prompt, system_prompt),
            "stream":   False,
            "options":  {"temperature": temperature, "num_predict": max_tokens},
        }
        url  = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        data = await _http_post(url, payload, {}, self._TIMEOUT)
        return data["message"]["content"]


# ─────────────────────────────────────────────
# Registry & factory
# ─────────────────────────────────────────────

_ADAPTER_MAP: dict[str, type[ModelAdapter]] = {
    "deploy_ai":  DeployAIAdapter,
    "openai":     OpenAIAdapter,
    "anthropic":  AnthropicAdapter,
    "groq":       GroqAdapter,
    "openrouter": OpenRouterAdapter,
    "ollama":     OllamaAdapter,
}


def get_model_adapter(provider: Optional[str] = None) -> ModelAdapter:
    """
    Return the configured ModelAdapter instance.

    provider='auto' triggers priority-based selection:
        groq        — fastest (if GROQ_API_KEY set)
        openrouter  — most models (if OPENROUTER_API_KEY set)
        openai      — if OPENAI_API_KEY set
        anthropic   — if ANTHROPIC_API_KEY set
        deploy_ai   — if DEPLOY_AI_CLIENT_ID set
        ollama      — always available locally
    """
    selected = (provider or settings.LLM_PROVIDER).lower().strip()
    if selected == "auto":
        selected = _auto_select_provider()

    adapter_cls = _ADAPTER_MAP.get(selected)
    if adapter_cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{selected}'. Valid: {list(_ADAPTER_MAP)}"
        )

    logger.info("[ModelAdapter] provider=%s", selected)
    return adapter_cls()


def list_models(provider: Optional[str] = None) -> dict[str, str]:
    """
    Return the model catalogue for a given provider, or all catalogues merged.

    Args:
        provider: 'groq' | 'openrouter' | None (returns combined)
    """
    catalogues: dict[str, dict[str, str]] = {
        "groq":       GROQ_MODELS,
        "openrouter": OPENROUTER_MODELS,
    }
    if provider:
        return catalogues.get(provider.lower(), {})
    return {
        f"{p}/{model}": desc
        for p, models in catalogues.items()
        for model, desc in models.items()
    }


def _auto_select_provider() -> str:
    """Priority: groq > openrouter > openai > anthropic > deploy_ai > ollama."""
    checks = [
        (settings.has_groq,                          "groq"),
        (settings.has_openrouter,                    "openrouter"),
        (settings.has_openai,                        "openai"),
        (settings.has_anthropic,                     "anthropic"),
        (bool(settings.DEPLOY_AI_CLIENT_ID.strip()), "deploy_ai"),
    ]
    for condition, name in checks:
        if condition:
            return name
    return "ollama"  # always available locally
