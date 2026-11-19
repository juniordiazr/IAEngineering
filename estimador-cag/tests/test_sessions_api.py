from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_session_store
from app.main import app
from app.sessions import SessionStore


@pytest.fixture
def store():
    store = SessionStore(max_turns=6)
    app.dependency_overrides[get_session_store] = lambda: store
    yield store
    app.dependency_overrides.clear()


def test_create_session_returns_uuid4(store):
    client = TestClient(app)
    response = client.post("/api/v1/sessions")
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    assert UUID(session_id).version == 4


def test_each_post_creates_a_new_independent_session(store):
    client = TestClient(app)
    a = client.post("/api/v1/sessions").json()["session_id"]
    b = client.post("/api/v1/sessions").json()["session_id"]
    assert a != b
    assert len(store) == 2
    assert store.get(a) is not store.get(b)