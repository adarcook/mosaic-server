from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from mosaic_server.models import MealAnalysisResponse, MealItem, NutritionEstimate
from mosaic_server.translator import ArgosTextTranslator, TextTranslator, TranslationError

logger = logging.getLogger(__name__)


class MealAnalyzer(Protocol):
    def analyze(self, filename: str, image_bytes: bytes) -> MealAnalysisResponse: ...


class MealAnalyzerError(RuntimeError):
    """Raised when an external meal-analysis provider cannot return a valid result."""


class MockMealAnalyzer:
    """Deterministic placeholder used for development and automated tests."""

    def analyze(self, filename: str, image_bytes: bytes) -> MealAnalysisResponse:
        digest = sha256(image_bytes).hexdigest()[:12]
        return MealAnalysisResponse(
            analysis_id=f"mock-{digest}",
            status="needs_confirmation",
            items=[
                MealItem(
                    name="תמונת ארוחה התקבלה",
                    estimated_quantity="הכמות אינה ידועה",
                    confidence=0.25,
                )
            ],
            nutrition=NutritionEstimate(
                calories_kcal=0,
                protein_g=0,
                carbohydrates_g=0,
                fat_g=0,
            ),
            assumptions=[
                f"נעשה שימוש בניתוח דמה עבור הקובץ {filename}.",
                "לא חושבו ערכים תזונתיים משום שלא מחובר מנתח תמונות אמיתי.",
            ],
            confirmation_questions=[
                "אילו מזונות מופיעים בתמונה?",
                "מהן הכמויות המשוערות?",
            ],
        )


class CodexCliMealAnalyzer:
    """Analyze a meal image with Codex and localize its text independently."""

    def __init__(
        self,
        executable: str = "codex",
        timeout_seconds: int = 120,
        model: str | None = None,
        translator: TextTranslator | None = None,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.translator = translator or ArgosTextTranslator()

    def analyze(self, filename: str, image_bytes: bytes) -> MealAnalysisResponse:
        digest = sha256(image_bytes).hexdigest()[:12]
        suffix = Path(filename).suffix.lower() or ".jpg"

        with tempfile.TemporaryDirectory(prefix="mosaic-meal-") as temp_dir:
            workdir = Path(temp_dir)
            image_path = workdir / f"meal{suffix}"
            schema_path = workdir / "meal-analysis.schema.json"
            output_path = workdir / "meal-analysis.json"

            image_path.write_bytes(image_bytes)
            schema_path.write_text(
                json.dumps(MealAnalysisResponse.model_json_schema()),
                encoding="utf-8",
            )

            self._run_codex(
                workdir=workdir,
                schema_path=schema_path,
                output_path=output_path,
                prompt=self._prompt(digest),
                image_path=image_path,
            )
            original = self._read_result(output_path, digest)

        return self._translate_user_facing_text(original)

    def _translate_user_facing_text(
        self, result: MealAnalysisResponse
    ) -> MealAnalysisResponse:
        try:
            items = [
                MealItem(
                    name=self._translate_if_needed(item.name),
                    estimated_quantity=self._translate_if_needed(item.estimated_quantity),
                    confidence=item.confidence,
                )
                for item in result.items
            ]
            assumptions = [self._translate_if_needed(value) for value in result.assumptions]
            questions = [
                self._translate_if_needed(value) for value in result.confirmation_questions
            ]
        except TranslationError as exc:
            logger.warning(
                "Local Hebrew translation failed; returning the original valid analysis: %s",
                exc,
            )
            return result

        translated = result.model_copy(
            update={
                "items": items,
                "assumptions": assumptions,
                "confirmation_questions": questions,
            }
        )
        if not self._has_hebrew_user_facing_text(translated):
            logger.warning(
                "Local translator returned non-Hebrew text; returning the original valid analysis"
            )
            return result
        return translated

    def _translate_if_needed(self, value: str) -> str:
        if re.search(r"[\u0590-\u05FF]", value):
            return value
        return self.translator.translate(value, "en", "he")

    def _run_codex(
        self,
        *,
        workdir: Path,
        schema_path: Path,
        output_path: Path,
        prompt: str,
        image_path: Path,
    ) -> None:
        output_path.unlink(missing_ok=True)
        command = [
            self.executable,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--image",
            str(image_path),
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
        ]
        if self.model:
            command.extend(["--model", self.model])
        command.append(prompt)

        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MealAnalyzerError(
                f"Codex CLI executable was not found: {self.executable}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise MealAnalyzerError(
                f"Codex CLI analysis exceeded {self.timeout_seconds} seconds"
            ) from exc

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise MealAnalyzerError(
                f"Codex CLI exited with code {completed.returncode}: {detail}"
            )
        if not output_path.exists():
            raise MealAnalyzerError("Codex CLI did not create the expected JSON output")

    @staticmethod
    def _read_result(output_path: Path, digest: str) -> MealAnalysisResponse:
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            payload["analysis_id"] = payload.get("analysis_id") or f"codex-{digest}"
            return MealAnalysisResponse.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise MealAnalyzerError("Codex CLI returned invalid meal-analysis JSON") from exc

    @staticmethod
    def _has_hebrew_user_facing_text(result: MealAnalysisResponse) -> bool:
        values = [
            *(item.name for item in result.items),
            *(item.estimated_quantity for item in result.items),
            *result.assumptions,
            *result.confirmation_questions,
        ]
        return bool(values) and all(re.search(r"[\u0590-\u05FF]", value) for value in values)

    @staticmethod
    def _prompt(digest: str) -> str:
        return f"""
Analyze the attached meal photo for Mosaic Fit.

Return only data matching the supplied JSON schema. Use analysis_id "codex-{digest}".
Identify visible foods and estimate quantities conservatively. Estimate total calories,
protein, carbohydrates, and fat. Set status to "needs_confirmation" whenever ingredients,
preparation method, oils, sauces, or quantities are uncertain. Put uncertainties in
assumptions and ask concise, actionable confirmation questions. Never claim certainty
from the image alone and never invent hidden ingredients.

Use clear English for user-facing text. Localization is handled separately by the server.
""".strip()
