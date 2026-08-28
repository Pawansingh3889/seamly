"""Configuration, loaded from the environment with the SEAMLY_ prefix."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEAMLY_", env_file=".env", extra="ignore")

    # Empty by default: a deploy without a database renders a clear 503
    # instead of crashing. Local dev sets it via .env (see .env.example).
    database_url: str = ""
    session_secret: str = "dev-secret-change-me"
    fixture_dir: str = "data/fixtures/generic"
    auto_seed: bool = True
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
