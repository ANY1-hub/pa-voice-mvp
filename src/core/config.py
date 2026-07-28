"""Central application settings (secrets + configuration)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / ``.env`` file.

    Secrets must never be committed. Use ``.env`` for local development.

    Attributes:
        openai_api_key: OpenAI API key (optional; required for chat/embeddings).
        xai_api_key: xAI / Grok API key (optional).
        mongodb_uri: MongoDB connection URI.
        secret_key: JWT signing key (required, no default).
        mongodb_db_name: Database name (default ``jarvis_db``).
        llm_model: OpenAI chat model name.
        embedding_model: OpenAI embedding model name.
        grok_model: Grok model name.
        access_token_expire_minutes: JWT lifetime in minutes (default 24h).
        whisper_model: faster-whisper model size (``base`` / ``small`` / …).
        piper_voice_en: Path to British-English Piper voice.
        piper_voice_de: Path to German Piper voice.
        piper_voice_hu: Path to Hungarian Piper voice.
    """

    # --- Secrets ---
    openai_api_key: str | None = None
    xai_api_key: str | None = None
    mongodb_uri: str = "mongodb://pa_admin:change-me@localhost:27017/?authSource=admin"
    secret_key: str  # JWT signing key – must not have a default value

    # --- Non-secret configuration ---
    mongodb_db_name: str = "jarvis_db"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    grok_model: str = "grok-2-latest"
    access_token_expire_minutes: int = 1440  # 24 hours
    # STT
    whisper_model: str = "base"  # base | small | medium (CPU: base/small + int8)
    # TTS – one voice per language (British English default for en)
    piper_voice_en: str = "voice_models/piper/en_US-amy-medium.onnx"
    piper_voice_de: str = "voice_models/piper/de_DE-thorsten-medium.onnx"
    piper_voice_hu: str = "voice_models/piper/hu_HU-anna-medium.onnx"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Returns:
        Application-wide ``Settings`` singleton (loaded once per process).
    """
    return Settings()
