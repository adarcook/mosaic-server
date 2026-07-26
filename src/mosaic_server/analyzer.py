from __future__ import annotations

import json
import re
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from mosaic_server.models import MealAnalysisResponse, MealItem, NutritionEstimate


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
    """Analyze a meal image by invoking Codex CLI in non-interactive mode."""

    def __init__(
        self,
        executable: str = "codex",
        timeout_seconds: int = 120,
        model: str | None = None,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.model = model

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
            result = self._read_result(output_path, digest)

            if not self._has_hebrew_user_facing_text(result):
                source_json = result.model_dump_json(indent=2)
                self._run_codex(
                    workdir=workdir,
                    schema_path=schema_path,
                    output_path=output_path,
                    prompt=self._hebrew_rewrite_prompt(source_json),
                )
                result = self._read_result(output_path, digest)

            if not self._has_hebrew_user_facing_text(result):
                raise MealAnalyzerError(
                    "Codex CLI returned user-facing meal text that is not in Hebrew"
                )

            return result

    def _run_codex(
        self,
        *,
        workdir: Path,
        schema_path: Path,
        output_path: Path,
        prompt: str,
        image_path: Path | None = None,
    ) -> None:
        command = [
            self.executable,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
        ]
        if image_path is not None:
            command.extend(["--image", str(image_path)])
        command.extend(
            [
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
            ]
        )
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
All user-facing text values must be written in clear, natural Hebrew. This includes every
item name, estimated_quantity, assumption, and confirmation question. Do not return English
sentences or mixed Hebrew-English prose. Brand names, product names, units, and established
terms may remain in their original spelling only when translating them would reduce clarity,
but every user-facing field must still contain explanatory Hebrew text.
Write Hebrew quantities in a natural right-to-left form, for example "גביע אחד, כ-200 גרם".

Identify visible foods and estimate quantities conservatively. Estimate total calories,
protein, carbohydrates, and fat. Set status to "needs_confirmation" whenever ingredients,
preparation method, oils, sauces, or quantities are uncertain. Put uncertainties in
assumptions and ask concise, actionable confirmation questions. Never claim certainty
from the image alone and never invent hidden ingredients.
""".strip()

    @staticmethod
    def _hebrew_rewrite_prompt(source_json: str) -> str:
        return f"""
Rewrite the following meal-analysis JSON so every user-facing text value is in natural Hebrew.
Return only JSON matching the supplied schema.

Translate every item name, estimated_quantity, assumption, and confirmation question.
Preserve analysis_id, status, confidence values, nutrition numbers, item order, and meaning.
Brand names such as Danone PRO may remain unchanged, but surround them with Hebrew descriptive
text. Every user-facing string must contain Hebrew characters. Do not add or remove facts.

Source JSON:
{source_json}
""".strip()
