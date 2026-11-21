"""Render del prompt conversacional (v2+): system con project_metadata y user con adjuntos.

Es independiente de ``loader.py`` (v1) porque el endpoint de sesiones no recibe los campos
del formulario (tipo de proyecto, nivel de detalle...). Usa el mismo entorno Jinja
(StrictUndefined, trim_blocks, lstrip_blocks) y la misma validación de versión.
"""

import re
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.sessions import ProjectMetadata

PROMPTS_DIR = Path(__file__).parent / "estimation"
_VERSION_RE = re.compile(r"^v\d+$")


@lru_cache
def _environment(version: str) -> Environment:
    if not _VERSION_RE.fullmatch(version):
        raise ValueError(f"Versión de prompt inválida: {version!r}")
    directory = PROMPTS_DIR / version
    if not directory.is_dir():
        raise ValueError(f"No existe la versión de prompt: {version!r}")
    return Environment(
        loader=FileSystemLoader(str(directory), encoding="utf-8-sig"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _neutralize(text: str, tag: str) -> str:
    """Impide que el input del usuario abra o cierre nuestras etiquetas de delimitación."""
    return re.sub(
        rf"<(/?)\s*{tag}\s*>",
        lambda m: f"&lt;{m.group(1)}{tag}&gt;",
        text,
        flags=re.IGNORECASE,
    )


def render_session_prompt(
    transcript: str,
    project_metadata: ProjectMetadata | None = None,
    attachments_text: str = "",
    version: str = "v2",
) -> tuple[str, str]:
    """Devuelve ``(system_prompt, user_prompt)`` para un turno de la conversación."""
    env = _environment(version)
    metadata = None
    if project_metadata is not None and not project_metadata.is_empty():
        metadata = project_metadata.model_dump()
    system = env.get_template("system.j2").render(project_metadata=metadata)
    user = env.get_template("user.j2").render(
        transcript=_neutralize(transcript, "transcript"),
        attachments_text=_neutralize(attachments_text, "attachments"),
    )
    return system, user