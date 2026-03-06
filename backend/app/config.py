"""Application configuration from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in project root (parent of backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    database_url: str = "sqlite:///./data/coach.db"
    # Scheduler: 1 day in seconds. Set to 60 for demo (1 min = 1 day). Default 86400 = real day.
    scheduler_day_seconds: int = 86400


def get_settings() -> Settings:
    return Settings()
