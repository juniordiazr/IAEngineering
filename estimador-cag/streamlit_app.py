import httpx
import streamlit as st
from pydantic import ValidationError

from app.config import settings
from app.schemas import (
    DetailLevel,
    EstimationRequest,
    EstimationResponse,
    OutputFormat,
    ProjectType,
)

ESTIMATE_URL = f"{settings.estimator_api_base_url.rstrip('/')}/api/v1/estimate"

PROJECT_TYPE_LABELS = {
    ProjectType.MOBILE_APP: "App móvil",
    ProjectType.WEB_SAAS: "Web / SaaS",
    ProjectType.INTERNAL_TOOL: "Herramienta interna",
    ProjectType.DATA_PIPELINE: "Pipeline de datos",
}
DETAIL_LEVEL_LABELS = {
    DetailLevel.SUMMARY: "Resumen",
    DetailLevel.MEDIUM: "Medio",
    DetailLevel.DETAILED: "Detallado",
}
OUTPUT_FORMAT_LABELS = {
    OutputFormat.PHASES_TABLE: "Tabla por fases",
    OutputFormat.LINE_ITEMS: "Lista de tareas",
    OutputFormat.NARRATIVE: "Texto narrativo",
}

st.set_page_config(page_title="Estimador de software", page_icon="🧮")

st.markdown(
    """
    <style>
        .block-container,
        [data-testid="stMainBlockContainer"] {
            padding-top: 2rem;
        }
        h1 {
            padding-top: 0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧮 Estimador de software")
st.caption("Describe el proyecto y elige cómo quieres recibir la estimación.")

with st.form("estimation_form"):
    description = st.text_area(
        "Descripción del proyecto",
        height=200,
        max_chars=2000,
        placeholder="Ej.: App móvil para reservar mesas en restaurantes, con pagos en línea...",
    )
    project_type = st.selectbox(
        "Tipo de proyecto", list(ProjectType), format_func=PROJECT_TYPE_LABELS.get
    )
    col1, col2 = st.columns(2)
    detail_level = col1.selectbox(
        "Nivel de detalle", list(DetailLevel), index=1, format_func=DETAIL_LEVEL_LABELS.get
    )
    output_format = col2.selectbox(
        "Formato de salida", list(OutputFormat), format_func=OUTPUT_FORMAT_LABELS.get
    )
    submitted = st.form_submit_button("Estimar")

if submitted:
    try:
        request = EstimationRequest(
            description=description.strip(),
            project_type=project_type,
            detail_level=detail_level,
            output_format=output_format,
        )
    except ValidationError:
        st.error("La descripción debe tener entre 20 y 2000 caracteres.")
    else:
        try:
            with st.spinner("Generando estimación..."):
                response = httpx.post(
                    ESTIMATE_URL, json=request.model_dump(mode="json"), timeout=120
                )
            response.raise_for_status()
            st.session_state.result = EstimationResponse.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            st.error(f"El servicio respondió {exc.response.status_code}: {exc.response.text}")
        except httpx.HTTPError as exc:
            st.error(
                f"No se pudo contactar con el servicio en {ESTIMATE_URL}. "
                f"¿Está corriendo uvicorn? ({exc})"
            )

result = st.session_state.get("result")
if result:
    st.divider()
    st.subheader("Estimación")
    st.caption(f"Versión del prompt: {result.prompt_version}")
    st.markdown(result.text)