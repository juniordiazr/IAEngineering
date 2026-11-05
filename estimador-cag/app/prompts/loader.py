import re
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.schemas import EstimationRequest

PROMPTS_DIR = Path(__file__).resolve().parent / "estimation"
DEFAULT_VERSION = "v1"
_VERSION_PATTERN = re.compile(r"^v\d+$")


@lru_cache
def _get_environment(version: str) -> Environment:
    if not _VERSION_PATTERN.match(version):
        raise ValueError(f"Versión de prompt inválida: {version!r} (usa v1, v2, ...)")
    version_dir = PROMPTS_DIR / version
    if not version_dir.is_dir():
        raise ValueError(f"No existe la versión de prompt {version!r} en {PROMPTS_DIR}")
    return Environment(
        loader=FileSystemLoader(str(version_dir), encoding="utf-8-sig"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_estimation_prompt(
    request: EstimationRequest, version: str = DEFAULT_VERSION
) -> tuple[str, str]:
    """Devuelve (system, user) renderizados para la versión de prompt indicada."""
    env = _get_environment(version)
    context = {
        "description": request.description,
        "project_type": request.project_type.value,
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
    }
    system = env.get_template("system.j2").render(**context).strip()
    user = env.get_template("user.j2").render(**context).strip()
    return system, user