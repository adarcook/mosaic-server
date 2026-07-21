from fastapi import FastAPI, File, HTTPException, UploadFile

from mosaic_server.analyzer import MealAnalyzerError
from mosaic_server.models import MealAnalysisResponse
from mosaic_server.settings import build_meal_analyzer

app = FastAPI(title="Mosaic Server", version="0.2.0")
analyzer = build_meal_analyzer()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "meal_analyzer": analyzer.__class__.__name__}


@app.post("/v1/meals/analyze", response_model=MealAnalysisResponse)
async def analyze_meal(image: UploadFile = File(...)) -> MealAnalysisResponse:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Unsupported image type")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Image is empty")
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB")

    try:
        return analyzer.analyze(filename=image.filename or "meal.jpg", image_bytes=payload)
    except MealAnalyzerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
