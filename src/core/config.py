"""Central application settings (secrets + configuration)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.

    Secrets must never be committed. Use .env for local development.
    """

    # --- Secrets ---
    openai_api_key: str | None = None
    xai_api_key: str | None = None
    mongodb_uri: str = "mongodb://pa_admin:change-me@localhost:27017/?authSource=admin""

    # --- Non-secret configuration ---
    mongodb_db_name: str = "jarvis_db"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    grok_model: str = "grok-2-latest"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
