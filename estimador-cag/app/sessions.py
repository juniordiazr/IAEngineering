"""Estado de las sesiones conversacionales del estimator.

Una sesión separa dos cosas que suelen confundirse:

- ``ConversationHistory``: los mensajes brutos (user/assistant) que viajan al LLM.
  Es una ventana deslizante: solo se conservan los últimos ``max_turns`` turnos.
- ``ProjectMetadata``: los hechos destilados del proyecto (nombre, equipo, tecnologías...).
  Vive aparte del historial, así que sobrevive cuando los turnos antiguos se descartan.

Las sesiones se guardan en un diccionario en memoria del proceso. Es una volatilidad
aceptada a propósito en esta fase: no hay base de datos ni Redis, se pierden al reiniciar
el servicio y no se comparten entre procesos. La persistencia pertenece a la fase de
despliegue. Como history y metadata son estructuras independientes, migrar a Redis o a
una base de datos solo cambiaría el almacén (``SessionStore``), no el modelo.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

DEFAULT_MAX_TURNS = 6

Message = dict[str, str]


class SessionNotFoundError(KeyError):
    """El session_id no existe (nunca se creó o el servicio se reinició)."""


class ProjectMetadata(BaseModel):
    """Hechos destilados del proyecto en curso. Sobreviven al truncado del historial."""

    project_name: str | None = None
    assumed_team_size: int | None = None
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = None
    explicit_constraints: list[str] = Field(default_factory=list)
    rejected_options: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            (
                self.project_name,
                self.assumed_team_size,
                self.mentioned_technologies,
                self.agreed_scope,
                self.explicit_constraints,
                self.rejected_options,
            )
        )


class ConversationHistory:
    """Ventana deslizante de turnos. Un turno es un par user + assistant.

    El system prompt NO se guarda aquí: se regenera en cada llamada a partir del
    ``ProjectMetadata`` actual (ver ``Session.to_messages_list``).
    """

    def __init__(self, max_turns: int = DEFAULT_MAX_TURNS):
        if max_turns < 1:
            raise ValueError("max_turns debe ser al menos 1")
        self.max_turns = max_turns
        self._messages: list[Message] = []

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        self._messages.append({"role": "user", "content": user_message})
        self._messages.append({"role": "assistant", "content": assistant_message})
        excess = len(self._messages) - self.max_turns * 2
        if excess > 0:
            del self._messages[:excess]  # descarta los pares más antiguos

    @property
    def turns(self) -> int:
        return len(self._messages) // 2

    def messages(self) -> list[Message]:
        return [dict(m) for m in self._messages]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Session:
    session_id: str
    history: ConversationHistory
    project_metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        self.history.add_turn(user_message, assistant_message)
        self.updated_at = _utcnow()

    def update_metadata(self, metadata: ProjectMetadata) -> None:
        self.project_metadata = metadata
        self.updated_at = _utcnow()

    def to_messages_list(
        self, system_prompt: str, user_message: str | None = None
    ) -> list[Message]:
        """Array ``messages`` listo para la API del LLM.

        ``system_prompt`` siempre va primero (invariante) y se pasa ya renderizado a partir
        del ``project_metadata`` actual. Después, la ventana de historial y, si se indica,
        el mensaje nuevo del usuario.
        """
        messages: list[Message] = [{"role": "system", "content": system_prompt}]
        messages.extend(self.history.messages())
        if user_message is not None:
            messages.append({"role": "user", "content": user_message})
        return messages


class SessionStore:
    """Almacén en memoria de sesiones, indexado por session_id."""

    def __init__(self, max_turns: int = DEFAULT_MAX_TURNS):
        self.max_turns = max_turns
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session = Session(
            session_id=str(uuid4()), history=ConversationHistory(self.max_turns)
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)