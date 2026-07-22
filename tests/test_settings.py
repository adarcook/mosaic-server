from pathlib import Path

import pytest
from pydantic import ValidationError

from mosaic_server.analyzer import CodexCliMealAnalyzer, MockMealAnalyzer
from mosaic_server.settings import Settings, build_meal_analyzer


def test_settings_defaults_to_mock() -> None:
    settings = Settings(_env_file=None)

    assert settings.meal_analyzer == "mock"
    assert isinstance(build_meal_analyzer(settings), MockMealAnalyzer)


def test_settings_loads_dotenv_and_builds_codex(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "MOSAIC_MEAL_ANALYZER=codex",
                "MOSAIC_CODEX_EXECUTABLE=C:/tools/codex.cmd",
                "MOSAIC_CODEX_TIMEOUT_SECONDS=240",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)
    analyzer = build_meal_analyzer(settings)

    assert settings.meal_analyzer == "codex"
    assert settings.codex_timeout_seconds == 240
    assert isinstance(analyzer, CodexCliMealAnalyzer)
    assert analyzer.executable == "C:/tools/codex.cmd"
    assert analyzer.timeout_seconds == 240


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MOSAIC_MEAL_ANALYZER=mock\n", encoding="utf-8")
    monkeypatch.setenv("MOSAIC_MEAL_ANALYZER", "codex")

    settings = Settings(_env_file=env_file)

    assert settings.meal_analyzer == "codex"


def test_invalid_timeout_fails_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOSAIC_CODEX_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
