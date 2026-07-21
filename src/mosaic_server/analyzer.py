from hashlib import sha256

from mosaic_server.models import MealAnalysisResponse, MealItem, NutritionEstimate


class MockMealAnalyzer:
    """Deterministic placeholder for the future Codex/image-analysis adapter."""

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
