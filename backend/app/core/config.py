"""
ATHENA - Core Configuration Settings
=====================================
pydantic-settings v2 syntax.

STUB_MODE:    when True, agents return deterministic demo data
              without real API calls. Auto-enabled when
              DEPLOY_AI_CLIENT_ID is empty.

LATS_ENABLED: enables Language Agent Tree Search for Scout and
              Strategy stages. Set to False for faster (linear)
              runs during development.

LLM_PROVIDER: selects the LLM backend used by agents.
              deploy_ai  — Deploy.AI platform (default, hackathon)
              openai     — OpenAI direct API
              anthropic  — Anthropic Claude direct API
              ollama     — Local models via Ollama (free)
"""
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME:    str  = "ATHENA Intelligence Orchestrator"
    APP_VERSION: str  = "1.0.0"
    DEBUG:       bool = True

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "*",
    ]

    # ── Deploy.AI / Complete.dev credentials ────────────────────
    DEPLOY_AI_AUTH_URL: str = "https://api-auth.dev.deploy.ai/oauth2/token"
    DEPLOY_AI_API_URL:  str = "https://core-api.dev.deploy.ai"
    DEPLOY_AI_CLIENT_ID:     str       = ""
    DEPLOY_AI_CLIENT_SECRET: SecretStr = SecretStr("")
    DEPLOY_AI_ORG_ID:        str       = ""

    # ── Agent IDs (from Deploy.AI Agent Builder) ────────────────
    SCOUT_AGENT_ID:    str = "SCOUT_AGENT_ID_PLACEHOLDER"
    STRATEGY_AGENT_ID: str = "STRATEGY_AGENT_ID_PLACEHOLDER"

    # ── Alternative LLM providers ───────────────────────────
    # Switch via LLM_PROVIDER env var (no code changes required).
    #
    # | Provider    | Env vars required                      |
    # |-------------|----------------------------------------|
    # | deploy_ai   | DEPLOY_AI_CLIENT_ID/SECRET/ORG_ID      |
    # | openai      | OPENAI_API_KEY                         |
    # | anthropic   | ANTHROPIC_API_KEY                      |
    # | ollama      | OLLAMA_BASE_URL, OLLAMA_MODEL (opt)    |
    LLM_PROVIDER:    str = "deploy_ai"   # deploy_ai | openai | anthropic | ollama

    # OpenAI direct
    OPENAI_API_KEY:  str = ""
    OPENAI_MODEL:    str = "gpt-4o"

    # Anthropic Claude direct
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL:   str = "claude-3-5-sonnet-20241022"

    # Ollama local (open-source, free, runs on GPU/CPU)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL:    str = "llama3.2"  # or qwen2.5, mistral, deepseek-r1

    # ── LATS (Language Agent Tree Search) settings ──────────────
    # Disabled automatically in stub mode (no API calls to multiply).
    LATS_ENABLED:            bool  = True
    LATS_N_CANDIDATES:       int   = 2     # parallel candidates per stage
    LATS_QUALITY_THRESHOLD:  float = 0.65  # score above which early-exit fires
    LATS_MAX_DEPTH:          int   = 2     # max reflection iterations

    # ── Reports output directory ────────────────────────────
    REPORTS_DIR: str = "./reports"

    # ── Stub / demo mode ────────────────────────────────
    STUB_MODE: bool = False

    # ── Derived properties ───────────────────────────────

    @property
    def is_stub_mode(self) -> bool:
        """True when STUB_MODE=True OR no Deploy.AI client ID is configured."""
        return self.STUB_MODE or not self.DEPLOY_AI_CLIENT_ID.strip()

    @property
    def effective_lats_enabled(self) -> bool:
        """LATS is disabled automatically in stub mode (nothing to score)."""
        return self.LATS_ENABLED and not self.is_stub_mode

    @property
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY.strip())

    @property
    def has_anthropic(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY.strip())

    # pydantic-settings v2
    model_config = SettingsConfigDict(
        env_file=".env",
        populate_by_name=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Module-level singleton (backward-compat import: `from app.core.config import settings`)
settings = get_settings()
