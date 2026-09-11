"""Central application settings (secrets + configuration)."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicit weak placeholders (case/trim insensitive; padded variants also fail).
_SECRET_KEY_PLACEHOLDERS = frozenset(
    {
        "change-me-to-a-long-random-string",
        "change-me",
    }
)
_MIN_SECRET_KEY_LEN = 64


class Settings(BaseSettings):
    """Application settings loaded from environment variables / ``.env`` file.

    Secrets must never be committed. Use ``.env`` for local development.

    Attributes:
        openai_api_key: OpenAI API key (optional; required for chat/embeddings).
        xai_api_key: xAI / Grok API key (optional).
        mongodb_uri: MongoDB connection URI.
        secret_key: JWT signing key (required, ≥64, no placeholder).
        mongodb_db_name: Database name (default ``jarvis_db``).
        llm_model: OpenAI chat model name.
        embedding_model: OpenAI embedding model name.
        grok_model: Grok model name.
        access_token_expire_minutes: JWT lifetime in minutes (default 24h).
        whisper_model: faster-whisper model size (``base`` / ``small`` / …).
        piper_voice_en: Path to British-English Piper voice.
        piper_voice_de: Path to German Piper voice.
        piper_voice_hu: Path to Hungarian Piper voice.
        login_max_attempts: Failed logins per IP+email before 429.
        login_window_seconds: Sliding window for that cap (default 15 min).
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
    piper_voice_en: str = "voice_models/piper/en_GB-alan-medium.onnx"
    piper_voice_de: str = "voice_models/piper/de_DE-thorsten-medium.onnx"
    piper_voice_hu: str = "voice_models/piper/hu_HU-anna-medium.onnx"
    login_max_attempts: int = Field(default=5, ge=1)
    login_window_seconds: int = Field(default=900, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("secret_key")
    @classmethod
    def _reject_weak_secret_key(cls, value: str) -> str:
        """Fail fast on empty, short, or placeholder JWT signing keys."""
        if not isinstance(value, str):
            raise ValueError("SECRET_KEY must be a string")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("SECRET_KEY must not be empty or whitespace-only")
        lowered = cleaned.casefold()
        if any(
            lowered == bad or lowered.startswith(bad)
            for bad in _SECRET_KEY_PLACEHOLDERS
        ):
            raise ValueError(
                "SECRET_KEY must not be a placeholder "
                "(e.g. change-me / change-me-to-a-long-random-string); "
                "set a random value of at least 64 characters"
            )
        if len(cleaned) < _MIN_SECRET_KEY_LEN:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_SECRET_KEY_LEN} characters"
            )
        return cleaned


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Returns:
        Application-wide ``Settings`` singleton (loaded once per process).
    """
    return Settings()  # type: ignore[call-arg]
