from pydantic import BaseModel, Field


class NutritionEstimate(BaseModel):
    calories_kcal: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbohydrates_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class MealItem(BaseModel):
    name: str
    estimated_quantity: str
    confidence: float = Field(ge=0, le=1)


class MealAnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    items: list[MealItem]
    nutrition: NutritionEstimate
    assumptions: list[str]
    confirmation_questions: list[str]
