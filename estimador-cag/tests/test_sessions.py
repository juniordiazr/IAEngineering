import pytest

from app.sessions import (
    ConversationHistory,
    ProjectMetadata,
    SessionNotFoundError,
    SessionStore,
)


def fill(history: ConversationHistory, turns: int) -> None:
    for i in range(1, turns + 1):
        history.add_turn(f"pregunta {i}", f"respuesta {i}")


def test_history_keeps_only_the_last_max_turns():
    history = ConversationHistory(max_turns=3)
    fill(history, 5)
    contents = [m["content"] for m in history.messages()]
    assert history.turns == 3
    assert contents == [
        "pregunta 3", "respuesta 3", "pregunta 4", "respuesta 4", "pregunta 5", "respuesta 5",
    ]


def test_history_below_limit_keeps_everything():
    history = ConversationHistory(max_turns=6)
    fill(history, 2)
    assert history.turns == 2
    assert len(history.messages()) == 4


def test_history_discards_whole_pairs_never_half_a_turn():
    history = ConversationHistory(max_turns=2)
    fill(history, 7)
    roles = [m["role"] for m in history.messages()]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_history_rejects_invalid_max_turns():
    with pytest.raises(ValueError):
        ConversationHistory(max_turns=0)


def test_messages_returns_a_copy():
    history = ConversationHistory()
    fill(history, 1)
    history.messages()[0]["content"] = "manipulado"
    assert history.messages()[0]["content"] == "pregunta 1"


def test_to_messages_list_starts_with_system_and_ends_with_new_user_message():
    session = SessionStore(max_turns=6).create()
    session.add_turn("hola", "buenas")
    messages = session.to_messages_list("SISTEMA", "mensaje nuevo")
    assert messages[0] == {"role": "system", "content": "SISTEMA"}
    assert messages[-1] == {"role": "user", "content": "mensaje nuevo"}
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]


def test_system_prompt_is_regenerated_on_every_call():
    session = SessionStore().create()
    first = session.to_messages_list("sistema v1")
    second = session.to_messages_list("sistema v2")
    assert first[0]["content"] == "sistema v1"
    assert second[0]["content"] == "sistema v2"


def test_eight_turns_never_exceed_the_configured_window():
    session = SessionStore(max_turns=6).create()
    for i in range(1, 9):
        messages = session.to_messages_list("SISTEMA", f"turno {i}")
        # system + ventana (máx. 6 pares) + mensaje nuevo
        assert len(messages) <= 1 + 6 * 2 + 1
        session.add_turn(f"turno {i}", f"respuesta {i}")
    assert session.history.turns == 6


def test_metadata_survives_history_truncation():
    session = SessionStore(max_turns=2).create()
    session.update_metadata(
        ProjectMetadata(project_name="BookFlow", mentioned_technologies=["Rails"])
    )
    for i in range(10):
        session.add_turn(f"u{i}", f"a{i}")
    assert session.history.turns == 2
    assert session.project_metadata.project_name == "BookFlow"
    assert session.project_metadata.mentioned_technologies == ["Rails"]


def test_project_metadata_is_empty_by_default_and_not_after_update():
    assert ProjectMetadata().is_empty() is True
    assert ProjectMetadata(project_name="BookFlow").is_empty() is False
    assert ProjectMetadata(mentioned_technologies=["Rails"]).is_empty() is False


def test_each_session_has_independent_state():
    store = SessionStore()
    a, b = store.create(), store.create()
    a.add_turn("solo en a", "ok")
    a.update_metadata(ProjectMetadata(project_name="A"))
    assert b.history.turns == 0
    assert b.project_metadata.is_empty()


def test_store_creates_unique_ids_and_returns_same_session():
    store = SessionStore()
    a, b = store.create(), store.create()
    assert a.session_id != b.session_id
    assert store.get(a.session_id) is a
    assert len(store) == 2


def test_unknown_session_raises():
    with pytest.raises(SessionNotFoundError):
        SessionStore().get("no-existe")


def test_add_turn_updates_updated_at():
    session = SessionStore().create()
    before = session.updated_at
    session.add_turn("hola", "buenas")
    assert session.updated_at >= before