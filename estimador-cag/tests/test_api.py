from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_service import build_system_prompt

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_docs_available():
    assert client.get("/docs").status_code == 200


def test_system_prompt_contains_examples():
    assert "Estimaciones previas de referencia" in build_system_prompt()


def test_estimate_with_mocked_llm(monkeypatch):
    async def fake(_transcription):
        return {"estimation": "## Estimación", "model": "gpt-4o-mini", "provider": "openai", "total_tokens": 10}

    monkeypatch.setattr("app.routers.estimations.generate_estimation", fake)
    r = client.post("/api/v1/estimate", json={"transcription": "Necesitamos una landing page con blog."})
    assert r.status_code == 200
    assert r.json()["provider"] == "openai"


def test_estimate_validates_body():
    assert client.post("/api/v1/estimate", json={}).status_code == 422