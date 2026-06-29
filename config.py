import uuid

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # ─── SecAudit API ──────────────────────────────────────
    API_KEY: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        validation_alias="SECAUDIT_API_KEY",
    )
    ALLOWED_ORIGINS: str = "http://localhost:8000"
    SECAUDIT_PORT: int = 8000
    MAX_UPLOAD_SIZE_MB: int = 10

    # ─── LLM Backend (openrouter | cli-proxy) ──────────────
    LLM_BACKEND: str = "openrouter"          # openrouter | cli-proxy
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash-preview-05-20"

    CLI_PROXY_URL: str = "http://host.docker.internal:8080/v1"
    CLI_PROXY_API_KEY: str = ""
    CLI_PROXY_MODEL: str = "local-model"


settings = Settings()
