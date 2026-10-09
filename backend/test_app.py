from fastapi.testclient import TestClient

from backend.main import CACHE, app

client = TestClient(app)

SOURCE_URL = "https://www.google.com/maps/place/Blue+Bottle+Coffee+%E2%80%94+Mint+Plaza"
SOURCE_KEY = "google-maps:blue-bottle-coffee-mint-plaza"


def setup_function() -> None:
    CACHE.clear()


def test_ingest_returns_summary() -> None:
    response = client.post("/api/ingest", json={"source_url": SOURCE_URL})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["business_name"] == "Blue Bottle Coffee — Mint Plaza"
    assert payload["dataset"]["summary"]["review_count"] == 1240
    assert payload["dataset"]["summary"]["average_rating"] == 4.3


def test_cache_reuses_original_dataset() -> None:
    first = client.post("/api/ingest", json={"source_url": SOURCE_URL})
    second = client.post("/api/ingest", json={"source_url": SOURCE_URL})
    assert first.json()["cache_hit"] is False
    assert second.json()["cache_hit"] is True


def test_scope_guard_rejects_out_of_scope_question() -> None:
    client.post("/api/ingest", json={"source_url": SOURCE_URL})
    response = client.post(
        "/api/chat",
        json={"source_key": SOURCE_KEY, "question": "What is the weather in San Francisco?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"
    assert "active Google Maps" in payload["answer"]


def test_supported_question_returns_answer() -> None:
    client.post("/api/ingest", json={"source_url": SOURCE_URL})
    response = client.post(
        "/api/chat",
        json={"source_key": SOURCE_KEY, "question": "What do customers like most about this place?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "food" in payload["answer"].lower()
