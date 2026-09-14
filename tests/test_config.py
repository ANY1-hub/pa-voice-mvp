from src.core.config import Settings, get_settings


def test_settings_defaults(monkeypatch):
    """Settings expose sensible defaults when no env vars are set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("MONGODB_DB_NAME", raising=False)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    settings = Settings(
        secret_key="unit-test-only-secret-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        _env_file=None,
    )

    assert settings.llm_model == "gpt-5-mini"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.mongodb_db_name == "jarvis_db"
    assert settings.openai_api_key is None
    assert settings.access_token_expire_minutes == 1440
    assert settings.login_max_attempts == 5
    assert settings.login_window_seconds == 900
    assert "http://127.0.0.1:5500" in settings.cors_origins
    assert "http://localhost:5500" in settings.cors_origins
    assert "*" not in settings.cors_origins


def test_settings_override_from_values(monkeypatch):
    """Settings can be constructed with explicit values."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    settings = Settings(
        openai_api_key="sk-test",
        llm_model="gpt-5-mini",
        mongodb_db_name="test_db",
        secret_key="unit-test-only-secret-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        _env_file=None,
    )
    assert settings.openai_api_key == "sk-test"
    assert settings.llm_model == "gpt-5-mini"
    assert settings.mongodb_db_name == "test_db"


def test_get_settings_returns_settings_instance():
    """get_settings() returns a cached Settings object."""
    settings = get_settings()
    assert isinstance(settings, Settings)
    # second call should return the same cached instance
    assert get_settings() is settings
