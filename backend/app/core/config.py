"""
ATHENA - Core Configuration Settings
=====================================
pydantic-settings v2 syntax.

STUB_MODE:    when True, agents return deterministic demo data
              without real API calls. Auto-enabled when
              DEPLOY_AI_CLIENT_ID is empty and no other LLM provider
              is configured.

LATS_ENABLED: enables Language Agent Tree Search for Scout/Strategy.
              Automatically disabled in stub mode.

LLM_PROVIDER: selects the LLM backend.
  deploy_ai   – Deploy.AI platform     (default, hackathon)
  openai      – OpenAI direct API
  anthropic   – Anthropic Claude direct API
  groq        – Groq LPU inference     (ultra-fast, free tier)
  openrouter  – OpenRouter gateway     (300+ models, free tier)
  ollama      – Local open-source      (free, private)
  auto        – pick best available
"""
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME:    str  = "ATHENA Intelligence Orchestrator"
    APP_VERSION: str  = "1.0.0"
    DEBUG:       bool = True

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "*",
    ]

    # ── Deploy.AI / Complete.dev ─────────────────────────────
    DEPLOY_AI_AUTH_URL: str = "https://api-auth.dev.deploy.ai/oauth2/token"
    DEPLOY_AI_API_URL:  str = "https://core-api.dev.deploy.ai"
    DEPLOY_AI_CLIENT_ID:     str       = ""
    DEPLOY_AI_CLIENT_SECRET: SecretStr = SecretStr("")
    DEPLOY_AI_ORG_ID:        str       = ""
    SCOUT_AGENT_ID:          str       = "SCOUT_AGENT_ID_PLACEHOLDER"
    STRATEGY_AGENT_ID:       str       = "STRATEGY_AGENT_ID_PLACEHOLDER"

    # ── LLM provider selection ─────────────────────────────
    # Change with one env-var — no code edits needed.
    LLM_PROVIDER: str = "deploy_ai"  # deploy_ai|openai|anthropic|groq|openrouter|ollama|auto

    # ── OpenAI ────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL:   str = "gpt-4o"  # gpt-4o | gpt-4o-mini | gpt-4-turbo

    # ── Anthropic Claude ───────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL:   str = "claude-3-5-sonnet-20241022"  # or claude-3-haiku-20240307

    # ── Groq  (ultra-fast LPU, generous free tier) ──────────
    # Get key: https://console.groq.com/keys
    # Free models: llama-3.3-70b-versatile | llama-3.1-8b-instant |
    #              mixtral-8x7b-32768 | gemma2-9b-it |
    #              deepseek-r1-distill-llama-70b
    GROQ_API_KEY: str = ""
    GROQ_MODEL:   str = "llama-3.3-70b-versatile"

    # ── OpenRouter  (300+ models, free tier available) ────────
    # Get key: https://openrouter.ai/keys
    # Free models (append :free): meta-llama/llama-3.3-70b-instruct:free
    #   google/gemma-2-9b-it:free | mistralai/mistral-7b-instruct:free
    #   deepseek/deepseek-r1:free | qwen/qwen-2-7b-instruct:free
    # Paid models: anthropic/claude-3.5-sonnet | openai/gpt-4o
    #   deepseek/deepseek-chat | google/gemini-flash-1.5
    OPENROUTER_API_KEY:   str = ""
    OPENROUTER_MODEL:     str = "meta-llama/llama-3.3-70b-instruct:free"
    OPENROUTER_SITE_URL:  str = ""      # optional — shown on openrouter.ai dashboard
    OPENROUTER_SITE_NAME: str = "ATHENA"

    # ── Ollama  (local, free, private) ─────────────────────
    # Install: https://ollama.ai | Pull: ollama pull llama3.2
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL:    str = "llama3.2"  # llama3.1:8b | mistral | qwen2.5:7b | deepseek-r1:7b

    # ── LATS settings ──────────────────────────────────
    LATS_ENABLED:           bool  = True
    LATS_N_CANDIDATES:      int   = 2     # parallel candidates per stage
    LATS_QUALITY_THRESHOLD: float = 0.65  # score ≥ this → early exit
    LATS_MAX_DEPTH:         int   = 2     # max reflection iterations

    # ── Misc ──────────────────────────────────────────
    REPORTS_DIR: str  = "./reports"
    STUB_MODE:   bool = False

    # ── Derived properties ────────────────────────────────

    @property
    def is_stub_mode(self) -> bool:
        """True when STUB_MODE=True OR no LLM provider is configured."""
        if self.STUB_MODE:
            return True
        # At least one real provider must be configured
        return not any([
            self.DEPLOY_AI_CLIENT_ID.strip(),
            self.has_groq,
            self.has_openrouter,
            self.has_openai,
            self.has_anthropic,
            # Ollama is always "available" locally — don't force stub if OLLAMA provider
            self.LLM_PROVIDER == "ollama",
        ])

    @property
    def effective_lats_enabled(self) -> bool:
        """LATS disabled automatically in stub mode."""
        return self.LATS_ENABLED and not self.is_stub_mode

    @property
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY.strip())

    @property
    def has_anthropic(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY.strip())

    @property
    def has_groq(self) -> bool:
        return bool(self.GROQ_API_KEY.strip())

    @property
    def has_openrouter(self) -> bool:
        return bool(self.OPENROUTER_API_KEY.strip())

    # pydantic-settings v2
    model_config = SettingsConfigDict(
        env_file=".env",
        populate_by_name=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Backward-compat: `from app.core.config import settings`
settings = get_settings()
