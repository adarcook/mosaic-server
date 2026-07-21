from fastapi.testclient import TestClient

from mosaic_server.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "meal_analyzer": "MockMealAnalyzer",
    }


def test_analyze_meal_accepts_jpeg() -> None:
    response = client.post(
        "/v1/meals/analyze",
        files={"image": ("meal.jpg", b"fake-jpeg-content", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_confirmation"
    assert body["analysis_id"].startswith("mock-")
    assert body["nutrition"]["calories_kcal"] == 0
    assert len(body["confirmation_questions"]) == 2


def test_analyze_meal_rejects_unsupported_content_type() -> None:
    response = client.post(
        "/v1/meals/analyze",
        files={"image": ("meal.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 415


def test_analyze_meal_rejects_empty_file() -> None:
    response = client.post(
        "/v1/meals/analyze",
        files={"image": ("meal.jpg", b"", "image/jpeg")},
    )

    assert response.status_code == 400
