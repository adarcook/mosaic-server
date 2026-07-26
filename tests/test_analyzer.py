import json
import subprocess
from pathlib import Path

import pytest

from mosaic_server.analyzer import CodexCliMealAnalyzer, MealAnalyzerError, MockMealAnalyzer
from mosaic_server.models import MealAnalysisResponse


def test_meal_analysis_schema_forbids_additional_properties() -> None:
    schema = MealAnalysisResponse.model_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["MealItem"]["additionalProperties"] is False
    assert schema["$defs"]["NutritionEstimate"]["additionalProperties"] is False


def test_codex_prompt_requires_hebrew_user_facing_text() -> None:
    prompt = CodexCliMealAnalyzer._prompt("test-digest")

    assert "All user-facing text values must be written in clear, natural Hebrew" in prompt
    assert "item name, estimated_quantity, assumption, and confirmation question" in prompt
    assert "Do not return English sentences or mixed Hebrew-English prose" in prompt


def test_mock_analyzer_returns_hebrew_content() -> None:
    result = MockMealAnalyzer().analyze("meal.jpg", b"image-bytes")

    assert result.items[0].name == "תמונת ארוחה התקבלה"
    assert result.confirmation_questions[0] == "אילו מזונות מופיעים בתמונה?"


def test_codex_analyzer_parses_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(
            json.dumps(
                {
                    "analysis_id": "codex-test",
                    "status": "needs_confirmation",
                    "items": [
                        {
                            "name": "חביתה",
                            "estimated_quantity": "שתי ביצים",
                            "confidence": 0.8,
                        }
                    ],
                    "nutrition": {
                        "calories_kcal": 220,
                        "protein_g": 15,
                        "carbohydrates_g": 2,
                        "fat_g": 16,
                    },
                    "assumptions": ["כמות השמן אינה ידועה."],
                    "confirmation_questions": ["האם השתמשת בשמן?"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CodexCliMealAnalyzer().analyze("meal.jpg", b"image-bytes")

    assert result.analysis_id == "codex-test"
    assert result.items[0].name == "חביתה"
    assert result.nutrition.protein_g == 15


def test_codex_analyzer_reports_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MealAnalyzerError, match="executable was not found"):
        CodexCliMealAnalyzer(executable="missing-codex").analyze(
            "meal.jpg", b"image-bytes"
        )
