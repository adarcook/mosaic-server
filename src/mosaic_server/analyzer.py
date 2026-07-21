from __future__ import annotations

import json
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
                    name="Meal photo received",
                    estimated_quantity="Unknown",
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
                f"Mock analysis was used for {filename}.",
                "No nutritional values are inferred until a real analyzer is connected.",
            ],
            confirmation_questions=[
                "What foods are visible in the photo?",
                "What are the approximate quantities?",
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
            command.append(self._prompt(digest))

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

            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
                payload["analysis_id"] = payload.get("analysis_id") or f"codex-{digest}"
                return MealAnalysisResponse.model_validate(payload)
            except (json.JSONDecodeError, ValidationError, TypeError) as exc:
                raise MealAnalyzerError("Codex CLI returned invalid meal-analysis JSON") from exc

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
""".strip()
