import json

import httpx
import pytest

from app.dependencies import get_session_store
from app.main import app
from app.routers import sessions as sessions_router
from app.services import metadata_extractor
from app.sessions import SessionStore
from tests.test_attachments import make_pdf

pytestmark = pytest.mark.anyio

PDF_TEXT = "Presupuesto maximo 50000 euros"


class ExtractorScript:
    """Respuestas programadas del extractor (generate_json) y prompts recibidos."""

    def __init__(self):
        self.replies: list[str] = []
        self.prompts: list[list[dict]] = []


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


@pytest.fixture(autouse=True)
def fake_extractor_llm(monkeypatch):
    """Evita llamadas reales del extractor. Sin respuesta programada, falla."""
    script = ExtractorScript()

    async def fake_generate_json(messages):
        script.prompts.append(messages)
        if not script.replies:
            raise RuntimeError("sin respuesta programada")
        return script.replies.pop(0)

    monkeypatch.setattr(metadata_extractor, "generate_json", fake_generate_json)
    return script


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


async def test_two_requests_update_project_metadata(
    client, fake_llm, fake_extractor_llm
):
    fake_extractor_llm.replies.extend(
        [
            json.dumps(
                {"project_name": "BookFlow", "mentioned_technologies": ["Rails"]}
            ),
            json.dumps(
                {
                    "project_name": "BookFlow",
                    "mentioned_technologies": ["Rails"],
                    "assumed_team_size": 4,
                }
            ),
        ]
    )
    sid = await new_session(client)

    first = await client.post(
        estimate_url(sid), data={"transcript": "Proyecto BookFlow con Rails"}
    )
    assert first.json()["project_metadata"]["project_name"] == "BookFlow"

    second = await client.post(
        estimate_url(sid), data={"transcript": "Somos 4 personas"}
    )
    metadata = second.json()["project_metadata"]
    assert metadata["project_name"] == "BookFlow"
    assert metadata["assumed_team_size"] == 4
    assert metadata["mentioned_technologies"] == ["Rails"]

    # La metadata del turno 1 llega al system prompt del turno 2, no al del turno 1.
    assert "<project_metadata>" not in fake_llm[0][0]["content"]
    system_turn_2 = fake_llm[1][0]["content"]
    assert "<project_metadata>" in system_turn_2
    assert "BookFlow" in system_turn_2


async def test_extractor_failure_keeps_previous_metadata(
    client, fake_llm, fake_extractor_llm
):
    fake_extractor_llm.replies.append(json.dumps({"project_name": "BookFlow"}))
    sid = await new_session(client)
    await client.post(estimate_url(sid), data={"transcript": "Proyecto BookFlow"})

    # Segundo turno: no hay respuesta programada, el extractor falla.
    second = await client.post(estimate_url(sid), data={"transcript": "gracias"})
    assert second.status_code == 200
    assert second.json()["project_metadata"]["project_name"] == "BookFlow"


async def test_attachment_text_reaches_the_extractor(
    client, fake_llm, fake_extractor_llm
):
    fake_extractor_llm.replies.append("{}")
    sid = await new_session(client)
    await client.post(
        estimate_url(sid),
        data={"transcript": "Estima esto"},
        files=pdf_upload(),
    )
    extractor_user_message = fake_extractor_llm.prompts[0][1]["content"]
    assert PDF_TEXT in extractor_user_message