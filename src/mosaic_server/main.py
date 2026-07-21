from fastapi import FastAPI, File, HTTPException, UploadFile

from mosaic_server.analyzer import MockMealAnalyzer
from mosaic_server.models import MealAnalysisResponse

app = FastAPI(title="Mosaic Server", version="0.1.0")
analyzer = MockMealAnalyzer()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/meals/analyze", response_model=MealAnalysisResponse)
async def analyze_meal(image: UploadFile = File(...)) -> MealAnalysisResponse:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Unsupported image type")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Image is empty")
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB")

    return analyzer.analyze(filename=image.filename or "meal.jpg", image_bytes=payload)
