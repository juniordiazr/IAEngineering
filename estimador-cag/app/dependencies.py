"""Dependencias compartidas de FastAPI."""

from functools import lru_cache

from app.config import settings
from app.sessions import SessionStore


@lru_cache
def get_session_store() -> SessionStore:
    """Un único almacén por proceso, compartido por todos los endpoints."""
    return SessionStore(max_turns=settings.session_max_turns)