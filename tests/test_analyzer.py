import json
import subprocess
from pathlib import Path

import pytest

from mosaic_server.analyzer import CodexCliMealAnalyzer, MealAnalyzerError
from mosaic_server.models import MealAnalysisResponse


def test_meal_analysis_schema_forbids_additional_properties() -> None:
    schema = MealAnalysisResponse.model_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["MealItem"]["additionalProperties"] is False
    assert schema["$defs"]["NutritionEstimate"]["additionalProperties"] is False


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
                            "name": "Omelette",
                            "estimated_quantity": "2 eggs",
                            "confidence": 0.8,
                        }
                    ],
                    "nutrition": {
                        "calories_kcal": 220,
                        "protein_g": 15,
                        "carbohydrates_g": 2,
                        "fat_g": 16,
                    },
                    "assumptions": ["Oil quantity is unknown."],
                    "confirmation_questions": ["Was oil used?"],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CodexCliMealAnalyzer().analyze("meal.jpg", b"image-bytes")

    assert result.analysis_id == "codex-test"
    assert result.items[0].name == "Omelette"
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
