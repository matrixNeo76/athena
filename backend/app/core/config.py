"""
ATHENA - Core configuration settings

pydantic-settings v2 syntax (SettingsConfigDict replaces deprecated inner Config class).

STUB_MODE: when True, Scout and Strategy agents return deterministic demo data
           without making any real API calls.  Auto-enabled when
           DEPLOY_AI_CLIENT_ID is not set (empty string).
"""
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str    = "ATHENA Intelligence Orchestrator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool      = True

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "*",
    ]

    # ── Deploy.AI / Complete.dev credentials ──────────────────────────────────
    DEPLOY_AI_AUTH_URL: str = "https://api-auth.dev.deploy.ai/oauth2/token"
    DEPLOY_AI_API_URL:  str = "https://core-api.dev.deploy.ai"
    DEPLOY_AI_CLIENT_ID:     str       = ""
    DEPLOY_AI_CLIENT_SECRET: SecretStr = SecretStr("")
    DEPLOY_AI_ORG_ID:        str       = ""

    # ── Agent IDs (from Agent Builder) ────────────────────────────────────────
    SCOUT_AGENT_ID:    str = "SCOUT_AGENT_ID_PLACEHOLDER"
    STRATEGY_AGENT_ID: str = "STRATEGY_AGENT_ID_PLACEHOLDER"

    # ── Reports output directory ──────────────────────────────────────────────
    REPORTS_DIR: str = "./reports"

    # ── Stub / demo mode ──────────────────────────────────────────────────────
    # Set STUB_MODE=true in .env to run the full pipeline without credentials.
    # Auto-enabled when DEPLOY_AI_CLIENT_ID is empty string.
    STUB_MODE: bool = False

    @property
    def is_stub_mode(self) -> bool:
        """True when STUB_MODE=True OR no Deploy.AI client ID is configured."""
        return self.STUB_MODE or not self.DEPLOY_AI_CLIENT_ID.strip()

    # pydantic-settings v2 — replaces deprecated inner Config class
    model_config = SettingsConfigDict(
        env_file=".env",
        populate_by_name=True,
    )


settings = Settings()
