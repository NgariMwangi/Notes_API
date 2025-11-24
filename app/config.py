from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        populate_by_name=True,
    )
    
    database_url: str = Field(default="sqlite:///./notes.db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    rate_limit: int = Field(default=100, alias="RATE_LIMIT")
    rate_limit_window_seconds: int = Field(default=600, alias="RATE_LIMIT_WINDOW")
    note_cache_ttl_seconds: int = Field(default=300, alias="NOTE_CACHE_TTL")
    recent_notes_limit: int = Field(default=5, alias="RECENT_NOTES_LIMIT")


@lru_cache
def get_settings() -> Settings:
    return Settings()

