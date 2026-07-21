from pydantic import BaseModel, ConfigDict, Field


class StrictSchemaModel(BaseModel):
    """Base model that produces strict JSON schemas accepted by Codex."""

    model_config = ConfigDict(extra="forbid")


class NutritionEstimate(StrictSchemaModel):
    calories_kcal: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbohydrates_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class MealItem(StrictSchemaModel):
    name: str
    estimated_quantity: str
    confidence: float = Field(ge=0, le=1)


class MealAnalysisResponse(StrictSchemaModel):
    analysis_id: str
    status: str
    items: list[MealItem]
    nutrition: NutritionEstimate
    assumptions: list[str]
    confirmation_questions: list[str]
