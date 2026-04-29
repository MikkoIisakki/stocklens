"""Application configuration — single source of truth for all settings.

All values come from environment variables. No scattered os.environ.get() calls
anywhere else in the codebase. Import Settings and use it.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str

    # Application
    log_level: str = "INFO"
    environment: str = "development"

    # Ingest staleness threshold — health check returns degraded if exceeded
    max_ingest_age_hours: int = 25

    # ENTSO-E Transparency Platform — day-ahead electricity prices.
    # Register at https://transparency.entsoe.eu (Settings → Web API Security Token).
    # Empty string means "not configured" — energy ingest will fail with a clear
    # error rather than crashing the whole app at import time.
    entsoe_api_token: SecretStr = SecretStr("")

    # Master API key — bypasses the api_key DB lookup when set. Intended for
    # local dev and bootstrap; production keys should live in the api_key table
    # (issue with `python -m app.tools.create_api_key`). Empty string disables
    # the master path entirely. See ADR-007.
    master_api_key: SecretStr = SecretStr("")


settings = Settings()
