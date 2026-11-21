"""Extracción local de texto de adjuntos (Camino B: pypdf + python-docx).

El contenido de un adjunto es INPUT del usuario, no instrucciones del programa. Por eso
este módulo solo extrae texto y lo delimita con ``--- attachment: <nombre> ---``; el
template del prompt lo envuelve además en un bloque ``<attachments>`` y le dice al modelo
que lo trate como datos. También pone límites de tamaño, de caracteres y de cantidad,
porque cada carácter extra es costo en tokens y latencia.
"""

import io
import re
from pathlib import PurePosixPath

from docx import Document
from pypdf import PdfReader

MAX_ATTACHMENTS = 5
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_CHARS_PER_FILE = 20_000
SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
TRUNCATION_NOTE = "[... texto truncado por límite de longitud ...]"
EMPTY_NOTE = "(el archivo no contiene texto extraíble)"


class AttachmentError(ValueError):
    """Adjunto inválido: tipo no soportado, demasiado grande o ilegible."""


def safe_filename(filename: str) -> str:
    """Solo el nombre base, sin saltos de línea (el nombre también es input del usuario)."""
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    return re.sub(r"[\x00-\x1f]", " ", name).strip() or "sin-nombre"


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx(content: bytes) -> str:
    document = Document(io.BytesIO(content))
    lines = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def extract_text(
    filename: str, content: bytes, max_chars: int = MAX_CHARS_PER_FILE
) -> str:
    name = safe_filename(filename)
    extension = PurePosixPath(name.lower()).suffix
    if extension not in SUPPORTED_EXTENSIONS:
        raise AttachmentError(
            f"'{name}': tipo no soportado (solo .pdf y .docx; "
            "un .doc antiguo hay que guardarlo como .docx)"
        )
    if len(content) > MAX_FILE_BYTES:
        raise AttachmentError(
            f"'{name}': supera el máximo de {MAX_FILE_BYTES // (1024 * 1024)} MB"
        )
    try:
        if extension == ".pdf":
            text = _extract_pdf(content)
        else:
            text = _extract_docx(content)
    except Exception as exc:  # archivo corrupto: cada librería lanza errores distintos
        raise AttachmentError(
            f"'{name}': no se pudo leer el archivo ({exc.__class__.__name__})"
        ) from exc

    text = text.strip()
    if not text:
        return EMPTY_NOTE  # p. ej. un PDF escaneado, que necesitaría OCR
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n" + TRUNCATION_NOTE
    return text


def build_attachments_text(files: list[tuple[str, bytes]]) -> str:
    """Concatena los adjuntos separados por ``--- attachment: <nombre> ---``.

    Devuelve cadena vacía si no hay adjuntos.
    """
    if len(files) > MAX_ATTACHMENTS:
        raise AttachmentError(f"Máximo {MAX_ATTACHMENTS} adjuntos por petición")
    parts = []
    for filename, content in files:
        name = safe_filename(filename)
        parts.append(f"--- attachment: {name} ---\n{extract_text(name, content)}")
    return "\n\n".join(parts)