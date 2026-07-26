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
    assert "every user-facing field must still contain explanatory Hebrew text" in prompt


def test_mock_analyzer_returns_hebrew_content() -> None:
    result = MockMealAnalyzer().analyze("meal.jpg", b"image-bytes")

    assert result.items[0].name == "תמונת ארוחה התקבלה"
    assert result.confirmation_questions[0] == "אילו מזונות מופיעים בתמונה?"


def test_codex_analyzer_parses_structured_hebrew_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(
            json.dumps(_hebrew_payload(), ensure_ascii=False),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CodexCliMealAnalyzer().analyze("meal.jpg", b"image-bytes")

    assert result.analysis_id == "codex-test"
    assert result.items[0].name == "חביתה"
    assert result.nutrition.protein_g == 15


def test_codex_analyzer_rewrites_english_output_in_hebrew(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        output_path = Path(command[command.index("-o") + 1])
        if calls == 2:
            source_path = Path(kwargs["cwd"]) / "meal-analysis-source.json"
            assert source_path.exists()
            assert json.loads(source_path.read_text(encoding="utf-8"))["nutrition"][
                "calories_kcal"
            ] == 220
        payload = _english_payload() if calls == 1 else _hebrew_payload()
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CodexCliMealAnalyzer().analyze("meal.jpg", b"image-bytes")

    assert calls == 2
    assert result.items[0].name == "חביתה"
    assert result.nutrition.calories_kcal == 220
    assert result.confirmation_questions == ["האם השתמשת בשמן?"]


def test_codex_analyzer_rejects_rewrite_that_changes_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        output_path = Path(command[command.index("-o") + 1])
        payload = _english_payload() if calls == 1 else _broken_rewrite_payload()
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MealAnalyzerError, match="changed the original meal analysis"):
        CodexCliMealAnalyzer().analyze("meal.jpg", b"image-bytes")


def test_codex_analyzer_rejects_english_after_rewrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(json.dumps(_english_payload()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MealAnalyzerError, match="not in Hebrew"):
        CodexCliMealAnalyzer().analyze("meal.jpg", b"image-bytes")


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


def _hebrew_payload() -> dict[str, object]:
    return {
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
    }


def _english_payload() -> dict[str, object]:
    return {
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


def _broken_rewrite_payload() -> dict[str, object]:
    return {
        "analysis_id": "codex-test",
        "status": "needs_confirmation",
        "items": [],
        "nutrition": {
            "calories_kcal": 0,
            "protein_g": 0,
            "carbohydrates_g": 0,
            "fat_g": 0,
        },
        "assumptions": ["לא צורף קובץ JSON לניתוח."],
        "confirmation_questions": ["אפשר להדביק כאן את ה-JSON?"],
    }
