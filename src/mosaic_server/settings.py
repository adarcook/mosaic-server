from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mosaic_server.analyzer import CodexCliMealAnalyzer, MealAnalyzer, MockMealAnalyzer


class Settings(BaseSettings):
    """Validated Mosaic Server configuration.

    Real environment variables override values loaded from the local .env file.
    Production deployments should inject environment variables through the service
    manager rather than storing deployment configuration in the repository.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MOSAIC_",
        case_sensitive=False,
        extra="ignore",
    )

    meal_analyzer: Literal["mock", "codex"] = "mock"
    codex_executable: str = "codex"
    codex_timeout_seconds: int = Field(default=120, ge=1, le=900)
    codex_model: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def build_meal_analyzer(settings: Settings | None = None) -> MealAnalyzer:
    config = settings or get_settings()

    if config.meal_analyzer == "mock":
        return MockMealAnalyzer()

    return CodexCliMealAnalyzer(
        executable=config.codex_executable,
        timeout_seconds=config.codex_timeout_seconds,
        model=config.codex_model,
    )
