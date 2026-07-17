from src.core.config import Settings, get_settings


def test_settings_defaults():
    """Settings expose sensible defaults when no env vars are set."""
    settings = Settings(
        _env_file=None,  # ignore real .env for this unit test
    )
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.mongodb_db_name == "jarvis_db"
    assert settings.openai_api_key is None


def test_settings_override_from_values():
    """Settings can be constructed with explicit values."""
    settings = Settings(
        openai_api_key="sk-test",
        llm_model="gpt-4o",
        mongodb_db_name="test_db",
        _env_file=None,
    )
    assert settings.openai_api_key == "sk-test"
    assert settings.llm_model == "gpt-4o"
    assert settings.mongodb_db_name == "test_db"


def test_get_settings_returns_settings_instance():
    """get_settings() returns a cached Settings object."""
    settings = get_settings()
    assert isinstance(settings, Settings)
    # second call should return the same cached instance
    assert get_settings() is settings
