import time

import streamlit as st
from openai import OpenAI

from app.config import settings
from app.context.examples import ESTIMATION_EXAMPLES
from app.services.llm_service import build_system_prompt

st.set_page_config(page_title="Estimador CAG", page_icon="🧮", layout="wide")
st.title("🧮 Estimador de software (CAG)")
st.caption("Pega la transcripción de una reunión y recibe una estimación.")


# --- API key: .env (vía settings) o .streamlit/secrets.toml; nunca en el código ---
def get_api_key() -> str:
    if settings.openai_api_key:
        return settings.openai_api_key
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return ""


api_key = get_api_key()
if not api_key:
    st.error("Falta OPENAI_API_KEY. Defínela en el archivo .env o en .streamlit/secrets.toml.")
    st.stop()

client = OpenAI(api_key=api_key)
MODEL = settings.llm_model
SYSTEM_PROMPT = build_system_prompt()  # el mismo prompt (con contexto CAG) del endpoint FastAPI

# --- Nivel 1: historial en session_state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# --- Nivel 2: streaming token a token ---
def stream_estimation(messages, metrics):
    start = time.perf_counter()
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        temperature=0.3,
        stream=True,
        stream_options={"include_usage": True},  # el último chunk trae los tokens
    )
    for chunk in stream:
        if chunk.model:
            metrics["model"] = chunk.model
        if chunk.usage:
            metrics["input_tokens"] = chunk.usage.prompt_tokens
            metrics["output_tokens"] = chunk.usage.completion_tokens
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
    metrics["seconds"] = time.perf_counter() - start


# --- Entrada del usuario ---
if prompt := st.chat_input("Pega aquí la transcripción de la reunión..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        metrics = {"model": MODEL}
        try:
            response = st.write_stream(stream_estimation(st.session_state.messages, metrics))
        except Exception as exc:
            st.error(f"Error llamando al LLM: {exc}")
            st.session_state.messages.pop()  # evita dejar un mensaje sin respuesta
            response = None

    if response:
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.last_metrics = metrics

# --- Nivel 3: panel lateral (va al final para mostrar las métricas de esta misma ejecución) ---
with st.sidebar:
    st.header("Contexto CAG")

    st.subheader("System prompt activo")
    st.text_area("system_prompt", SYSTEM_PROMPT, height=250, disabled=True, label_visibility="collapsed")

    st.subheader("Contexto estático inyectado")
    for i, ex in enumerate(ESTIMATION_EXAMPLES, start=1):
        with st.expander(f"Ejemplo {i}"):
            st.markdown(f"**Resumen:** {ex['meeting_summary']}")
            st.markdown(ex["estimation"])

    st.subheader("Última llamada")
    m = st.session_state.last_metrics
    if m:
        st.markdown(f"**Modelo:** `{m.get('model', MODEL)}`")
        col1, col2, col3 = st.columns(3)
        col1.metric("Tokens in", m.get("input_tokens", "-"))
        col2.metric("Tokens out", m.get("output_tokens", "-"))
        col3.metric("Segundos", f"{m.get('seconds', 0):.1f}")
    else:
        st.caption("Aún no hay llamadas.")

    if st.button("Nueva conversación"):
        st.session_state.messages = []
        st.session_state.last_metrics = None
        st.rerun()