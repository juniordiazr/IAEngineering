from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_BODY = {
    "description": "Una app móvil para reservar mesas en restaurantes con pagos en línea.",
    "project_type": "mobile_app",
    "detail_level": "medium",
    "output_format": "phases_table",
}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_docs_available():
    assert client.get("/docs").status_code == 200


def test_estimate_with_mocked_llm(monkeypatch):
    captured = {}

    async def fake(system_prompt, user_prompt):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "## Estimación de prueba"

    monkeypatch.setattr("app.routers.estimations.generate_estimation", fake)
    r = client.post("/api/v1/estimate", json=VALID_BODY)

    assert r.status_code == 200
    assert r.json() == {"text": "## Estimación de prueba", "prompt_version": "v1"}
    # system y user llegan separados y cada uno con su contenido
    assert "phases_table" in captured["system"]
    assert "<project_description>" in captured["user"]
    assert VALID_BODY["description"] in captured["user"]


def test_estimate_validates_body():
    assert client.post("/api/v1/estimate", json={}).status_code == 422


def test_estimate_rejects_invalid_enum():
    body = {**VALID_BODY, "project_type": "otra_cosa"}
    assert client.post("/api/v1/estimate", json=body).status_code == 422