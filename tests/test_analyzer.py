import json
import subprocess
from pathlib import Path

import pytest

from mosaic_server.analyzer import CodexCliMealAnalyzer, MealAnalyzerError, MockMealAnalyzer
from mosaic_server.models import MealAnalysisResponse
from mosaic_server.translator import TranslationError


class FakeHebrewTranslator:
    translations = {
        "Omelette": "חביתה",
        "2 eggs": "שתי ביצים",
        "Oil quantity is unknown.": "כמות השמן אינה ידועה.",
        "Was oil used?": "האם השתמשת בשמן?",
    }

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        assert source_language == "en"
        assert target_language == "he"
        return self.translations[text]


class FailingTranslator:
    def translate(self, text: str, source_language: str, target_language: str) -> str:
        raise TranslationError("model is unavailable")


def test_meal_analysis_schema_forbids_additional_properties() -> None:
    schema = MealAnalysisResponse.model_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["MealItem"]["additionalProperties"] is False
    assert schema["$defs"]["NutritionEstimate"]["additionalProperties"] is False


def test_codex_prompt_leaves_localization_to_server() -> None:
    prompt = CodexCliMealAnalyzer._prompt("test-digest")

    assert "Use clear English for user-facing text" in prompt
    assert "Localization is handled separately by the server" in prompt


def test_mock_analyzer_returns_hebrew_content() -> None:
    result = MockMealAnalyzer().analyze("meal.jpg", b"image-bytes")

    assert result.items[0].name == "תמונת ארוחה התקבלה"
    assert result.confirmation_questions[0] == "אילו מזונות מופיעים בתמונה?"


def test_codex_analyzer_translates_only_user_facing_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(json.dumps(_english_payload()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CodexCliMealAnalyzer(translator=FakeHebrewTranslator()).analyze(
        "meal.jpg", b"image-bytes"
    )

    assert calls == 1
    assert result.items[0].name == "חביתה"
    assert result.items[0].estimated_quantity == "שתי ביצים"
    assert result.confirmation_questions == ["האם השתמשת בשמן?"]
    assert result.analysis_id == "codex-test"
    assert result.status == "needs_confirmation"
    assert result.items[0].confidence == 0.8
    assert result.nutrition.calories_kcal == 220
    assert result.nutrition.protein_g == 15


def test_codex_analyzer_does_not_translate_existing_hebrew(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnexpectedTranslator:
        def translate(self, text: str, source_language: str, target_language: str) -> str:
            raise AssertionError("translator should not be called for Hebrew text")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(
            json.dumps(_hebrew_payload(), ensure_ascii=False), encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CodexCliMealAnalyzer(translator=UnexpectedTranslator()).analyze(
        "meal.jpg", b"image-bytes"
    )

    assert result.items[0].name == "חביתה"
    assert result.nutrition.calories_kcal == 220


def test_codex_analyzer_falls_back_when_local_translation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(json.dumps(_english_payload()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = CodexCliMealAnalyzer(translator=FailingTranslator()).analyze(
        "meal.jpg", b"image-bytes"
    )

    assert result.items[0].name == "Omelette"
    assert result.nutrition.calories_kcal == 220


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
