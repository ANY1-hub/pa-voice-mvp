"""Shared pytest fixtures."""

import os

# --- Test isolation: never touch the production database name ---
os.environ["MONGODB_DB_NAME"] = "jarvis_test"
# SECRET_KEY already set below; keep it early
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only-32chars!")


from src.core.config import get_settings

get_settings.cache_clear()  # important: Settings is lru_cached
