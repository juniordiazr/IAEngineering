import httpx
import pytest
from tests.test_attachments import make_pdf

from app.dependencies import get_session_store
from app.main import app
from app.routers import sessions as sessions_router
from app.sessions import SessionStore

pytestmark = pytest.mark.anyio

PDF_TEXT = "Presupuesto maximo 50000 euros"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def store():
    store = SessionStore(max_turns=6)
    app.dependency_overrides[get_session_store] = lambda: store
    yield store
    app.dependency_overrides.clear()


@pytest.fixture
def fake_llm(monkeypatch):
    """Sustituye la llamada al LLM; guarda los mensajes de cada turno."""
    calls: list[list[dict]] = []

    async def fake_generate_chat(messages):
        calls.append(messages)
        return f"RESPUESTA {len(calls)}"

    monkeypatch.setattr(sessions_router, "generate_chat", fake_generate_chat)
    return calls


@pytest.fixture
async def client(store):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c


async def new_session(client) -> str:
    response = await client.post("/api/v1/sessions")
    return response.json()["session_id"]


def estimate_url(session_id: str) -> str:
    return f"/api/v1/sessions/{session_id}/estimate"


def pdf_upload():
    return [
        (
            "attachments",
            ("requisitos.pdf", make_pdf(PDF_TEXT), "application/pdf"),
        )
    ]


async def test_unknown_session_returns_404(client, fake_llm):
    response = await client.post(
        estimate_url("no-existe"), data={"transcript": "hola"}
    )
    assert response.status_code == 404
    assert fake_llm == []


async def test_first_turn_returns_estimate_and_stores_turn(
    client, fake_llm, store
):
    sid = await new_session(client)
    response = await client.post(
        estimate_url(sid), data={"transcript": "Reunión sobre BookFlow"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "RESPUESTA 1"
    assert body["turns"] == 1
    assert body["prompt_version"] == "v2"
    messages = fake_llm[0]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "Reunión sobre BookFlow" in messages[1]["content"]
    assert store.get(sid).history.turns == 1


async def test_second_turn_sends_the_previous_history(client, fake_llm):
    sid = await new_session(client)
    await client.post(estimate_url(sid), data={"transcript": "primer mensaje"})
    await client.post(estimate_url(sid), data={"transcript": "segundo mensaje"})
    messages = fake_llm[1]
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == "RESPUESTA 1"
    assert "segundo mensaje" in messages[3]["content"]


async def test_pdf_attachment_content_reaches_the_prompt(client, fake_llm):
    sid = await new_session(client)
    response = await client.post(
        estimate_url(sid),
        data={"transcript": "Estima esto"},
        files=pdf_upload(),
    )
    assert response.status_code == 200
    user_message = fake_llm[0][-1]["content"]
    assert "--- attachment: requisitos.pdf ---" in user_message
    assert PDF_TEXT in user_message


async def test_history_keeps_attachment_names_not_their_content(
    client, fake_llm, store
):
    sid = await new_session(client)
    await client.post(
        estimate_url(sid),
        data={"transcript": "Estima esto"},
        files=pdf_upload(),
    )
    stored = store.get(sid).history.messages()[0]["content"]
    assert "requisitos.pdf" in stored
    assert PDF_TEXT not in stored


async def test_unsupported_attachment_returns_422_and_stores_nothing(
    client, fake_llm, store
):
    sid = await new_session(client)
    files = [("attachments", ("notas.txt", b"hola", "text/plain"))]
    response = await client.post(
        estimate_url(sid), data={"transcript": "Estima esto"}, files=files
    )
    assert response.status_code == 422
    assert fake_llm == []
    assert store.get(sid).history.turns == 0


async def test_blank_transcript_returns_422(client, fake_llm):
    sid = await new_session(client)
    response = await client.post(estimate_url(sid), data={"transcript": "   "})
    assert response.status_code == 422
    assert fake_llm == []


async def test_llm_failure_returns_502_and_stores_nothing(
    client, store, monkeypatch
):
    async def broken(messages):
        raise RuntimeError("boom")

    monkeypatch.setattr(sessions_router, "generate_chat", broken)
    sid = await new_session(client)
    response = await client.post(estimate_url(sid), data={"transcript": "hola"})
    assert response.status_code == 502
    assert store.get(sid).history.turns == 0


async def test_eight_turns_never_exceed_max_turns(client, fake_llm, store):
    sid = await new_session(client)
    for i in range(1, 9):
        response = await client.post(
            estimate_url(sid), data={"transcript": f"turno {i}"}
        )
        assert response.status_code == 200
    limit = 1 + 6 * 2 + 1
    assert all(len(messages) <= limit for messages in fake_llm)
    assert len(fake_llm[-1]) == limit
    assert store.get(sid).history.turns == 6