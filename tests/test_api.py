import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MOSAIC_MEAL_ANALYZER", "mock")
    monkeypatch.delenv("MOSAIC_CODEX_EXECUTABLE", raising=False)
    monkeypatch.delenv("MOSAIC_CODEX_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("MOSAIC_CODEX_MODEL", raising=False)

    import mosaic_server.main as main_module

    main_module = importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "meal_analyzer": "MockMealAnalyzer",
    }


def test_analyze_meal_accepts_jpeg(client: TestClient) -> None:
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


def test_analyze_meal_rejects_unsupported_content_type(client: TestClient) -> None:
    response = client.post(
        "/v1/meals/analyze",
        files={"image": ("meal.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 415


def test_analyze_meal_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/v1/meals/analyze",
        files={"image": ("meal.jpg", b"", "image/jpeg")},
    )

    assert response.status_code == 400
