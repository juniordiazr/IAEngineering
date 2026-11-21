import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.dependencies import get_session_store
from app.prompts.session_loader import render_session_prompt
from app.schemas import EstimationResponse
from app.services.attachments import (
    MAX_FILE_BYTES,
    AttachmentError,
    build_attachments_text,
    safe_filename,
)
from app.services.llm_service import generate_chat
from app.services.metadata_extractor import extract_metadata
from app.sessions import ProjectMetadata, SessionNotFoundError, SessionStore

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v2"
MAX_TRANSCRIPT_CHARS = 20_000

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreated(BaseModel):
    session_id: str


class SessionEstimateResponse(EstimationResponse):
    session_id: str
    turns: int
    project_metadata: ProjectMetadata


@router.post("", response_model=SessionCreated)
def create_session(
    store: SessionStore = Depends(get_session_store),
) -> SessionCreated:
    """Crea una conversación nueva y devuelve su session_id (uuid4)."""
    session = store.create()
    return SessionCreated(session_id=session.session_id)


def _history_entry(transcript: str, files: list[tuple[str, bytes]]) -> str:
    """Lo que se guarda en el historial: el texto y los NOMBRES de los adjuntos.

    El texto completo de los adjuntos viaja solo en el turno en que se sube:
    repetirlo en cada turno multiplicaría el costo en tokens. Los hechos que
    importan los conserva el project_metadata, que sobrevive al truncado.
    """
    if not files:
        return transcript
    names = ", ".join(safe_filename(name) for name, _ in files)
    return f"{transcript}\n\n[Adjuntos de este turno: {names}]"


@router.post("/{session_id}/estimate", response_model=SessionEstimateResponse)
async def estimate_in_session(
    session_id: str,
    transcript: str = Form(..., max_length=MAX_TRANSCRIPT_CHARS),
    attachments: list[UploadFile] = File(default=[]),
    store: SessionStore = Depends(get_session_store),
) -> SessionEstimateResponse:
    """Un turno de la conversación: texto + adjuntos opcionales (PDF/Word)."""
    try:
        session = store.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            404, "Sesión no encontrada. Crea una con POST /sessions."
        ) from None
    if not transcript.strip():
        raise HTTPException(422, "El texto no puede estar vacío.")

    files: list[tuple[str, bytes]] = []
    for upload in attachments:
        content = await upload.read(MAX_FILE_BYTES + 1)
        if upload.filename or content:  # algunos clientes mandan una parte vacía
            files.append((upload.filename or "", content))
    try:
        attachments_text = build_attachments_text(files)
    except AttachmentError as exc:
        raise HTTPException(422, str(exc)) from exc

    system_prompt, user_prompt = render_session_prompt(
        transcript, session.project_metadata, attachments_text
    )
    messages = session.to_messages_list(system_prompt, user_prompt)

    try:
        reply = await generate_chat(messages)
    except Exception:
        logger.exception("Fallo al llamar al LLM (sesión %s)", session_id)
        raise HTTPException(502, "No se pudo generar la estimación.") from None

    session.add_turn(_history_entry(transcript, files), reply)
    session.update_metadata(
        await extract_metadata(
            session.project_metadata, transcript, reply, attachments_text
        )
    )
    return SessionEstimateResponse(
        session_id=session_id,
        text=reply,
        prompt_version=PROMPT_VERSION,
        turns=session.history.turns,
        project_metadata=session.project_metadata,
    )