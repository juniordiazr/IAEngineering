from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_session_store
from app.sessions import SessionStore

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreated(BaseModel):
    session_id: str


@router.post("", response_model=SessionCreated)
def create_session(store: SessionStore = Depends(get_session_store)) -> SessionCreated:
    """Crea una conversación nueva y devuelve su session_id (uuid4)."""
    session = store.create()
    return SessionCreated(session_id=session.session_id)