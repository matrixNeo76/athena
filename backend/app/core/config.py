"""
ATHENA - Core configuration settings
TODO-1: Added Deploy.AI / Complete.dev credential fields
TODO-7: Added REPORTS_DIR for Presenter Service output
"""
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ATHENA Intelligence Orchestrator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080", "*"]

    STUB_STAGE_DELAY: float = 3.0

    # TODO-1: Deploy.AI / Complete.dev credentials
    DEPLOY_AI_AUTH_URL: str = "https://api-auth.dev.deploy.ai/oauth2/token"
    DEPLOY_AI_API_URL: str = "https://core-api.dev.deploy.ai"
    DEPLOY_AI_CLIENT_ID: str = ""
    DEPLOY_AI_CLIENT_SECRET: SecretStr = SecretStr("")
    DEPLOY_AI_ORG_ID: str = ""

    # TODO-7: Presenter Service report output directory
    REPORTS_DIR: str = "./reports"

    # TODO-1: Agent IDs
    SCOUT_AGENT_ID: str = "SCOUT_AGENT_ID_PLACEHOLDER"
    STRATEGY_AGENT_ID: str = "STRATEGY_AGENT_ID_PLACEHOLDER"

    class Config:
        env_file = ".env"
        populate_by_name = True


settings = Settings()
