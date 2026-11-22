"""Cliente Streamlit conversacional del Estimador CAG (sesión 5)."""

import httpx
import streamlit as st

from app.config import settings

API_BASE = settings.estimator_api_base_url.rstrip("/")
SESSIONS_URL = f"{API_BASE}/api/v1/sessions"
REQUEST_TIMEOUT = 120.0  # el turno hace dos llamadas al LLM (estimación + metadata)

METADATA_LABELS = [
    ("project_name", "Proyecto"),
    ("assumed_team_size", "Equipo"),
    ("mentioned_technologies", "Tecnologías"),
    ("agreed_scope", "Alcance"),
    ("explicit_constraints", "Restricciones"),
    ("rejected_options", "Opciones descartadas"),
]

st.set_page_config(page_title="Estimador CAG", layout="wide")
st.markdown(
    "<style>.block-container {padding-top: 1.5rem;}</style>",
    unsafe_allow_html=True,
)


def start_new_conversation() -> None:
    """Crea una sesión nueva en la API y reinicia el estado del cliente."""
    try:
        response = httpx.post(SESSIONS_URL, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        st.error(
            f"No se pudo crear la sesión en {API_BASE}. "
            f"¿Está levantado uvicorn? ({exc})"
        )
        st.stop()
    st.session_state.session_id = response.json()["session_id"]
    st.session_state.messages = []
    st.session_state.project_metadata = {}
    st.session_state.form_n = st.session_state.get("form_n", 0) + 1


def error_detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text


def send_turn(text: str, uploads: list) -> bool:
    """Envía un turno (multipart). Devuelve True si salió bien."""
    url = f"{SESSIONS_URL}/{st.session_state.session_id}/estimate"
    files = [
        ("attachments", (u.name, u.getvalue(), u.type or "application/octet-stream"))
        for u in uploads
    ]
    try:
        response = httpx.post(
            url,
            data={"transcript": text},
            files=files or None,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        st.error(f"No se pudo conectar con la API: {exc}")
        return False

    if response.status_code == 404:
        st.error(
            "La sesión ya no existe (¿se reinició el servidor?). "
            "Pulsa «Nueva conversación»."
        )
        return False
    if response.status_code != 200:
        st.error(f"Error {response.status_code}: {error_detail(response)}")
        return False

    body = response.json()
    st.session_state.messages.append(
        {"role": "user", "content": text, "attachments": [u.name for u in uploads]}
    )
    st.session_state.messages.append({"role": "assistant", "content": body["text"]})
    st.session_state.project_metadata = body["project_metadata"]
    return True


def render_metadata_panel() -> None:
    st.sidebar.subheader("Metadata del proyecto")
    metadata = st.session_state.project_metadata
    shown = False
    for key, label in METADATA_LABELS:
        value = metadata.get(key)
        if not value:
            continue
        if isinstance(value, list):
            value = ", ".join(value)
        st.sidebar.markdown(f"**{label}:** {value}")
        shown = True
    if not shown:
        st.sidebar.caption("Aún no hay datos del proyecto.")


# --- Estado de la sesión -------------------------------------------------------
if st.sidebar.button("Nueva conversación"):
    start_new_conversation()
if "session_id" not in st.session_state:
    start_new_conversation()
n = st.session_state.form_n  # cambia la clave de los campos para vaciarlos

st.title("Estimador CAG")

# --- Conversación + formulario ---------------------------------------------------
history_area = st.container()  # se rellena más abajo, tras procesar el envío

with st.form("turn_form"):
    text = st.text_area(
        "Describe el proyecto o responde con más detalle",
        key=f"text_{n}",
        height=140,
        max_chars=20_000,
    )
    uploads = st.file_uploader(
        "Adjuntos (PDF o Word)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key=f"files_{n}",
    )
    submitted = st.form_submit_button("Enviar")

if submitted:
    if not text.strip():
        st.warning("Escribe un mensaje antes de enviar.")
    else:
        with st.spinner("Estimando..."):
            ok = send_turn(text.strip(), uploads)
        if ok:
            st.session_state.form_n += 1
            st.rerun()

with history_area:
    if not st.session_state.messages:
        st.info("Empieza describiendo el proyecto. Puedes adjuntar PDF o Word.")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("attachments"):
                st.caption("Adjuntos: " + ", ".join(message["attachments"]))

render_metadata_panel()
turns = len(st.session_state.messages) // 2
st.sidebar.caption(f"Sesión {st.session_state.session_id[:8]} · turnos: {turns}")