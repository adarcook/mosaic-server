from __future__ import annotations

import os

from mosaic_server.analyzer import CodexCliMealAnalyzer, MealAnalyzer, MockMealAnalyzer


def build_meal_analyzer() -> MealAnalyzer:
    provider = os.getenv("MOSAIC_MEAL_ANALYZER", "mock").strip().lower()

    if provider == "mock":
        return MockMealAnalyzer()
    if provider == "codex":
        timeout_seconds = int(os.getenv("MOSAIC_CODEX_TIMEOUT_SECONDS", "120"))
        return CodexCliMealAnalyzer(
            executable=os.getenv("MOSAIC_CODEX_EXECUTABLE", "codex"),
            timeout_seconds=timeout_seconds,
            model=os.getenv("MOSAIC_CODEX_MODEL") or None,
        )

    raise ValueError(
        "Unsupported MOSAIC_MEAL_ANALYZER value. Expected 'mock' or 'codex'."
    )
