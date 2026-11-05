from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    "app/__init__.py", "app/main.py", "app/config.py", "app/schemas.py",
    "app/routers/__init__.py", "app/routers/estimations.py",
    "app/services/__init__.py", "app/services/llm_service.py",
    "app/prompts/__init__.py", "app/prompts/loader.py",
    "app/prompts/estimation/v1/system.j2",
    "app/prompts/estimation/v1/user.j2",
    "app/prompts/estimation/v1/examples.j2",
    ".env.example", ".gitignore", "pyproject.toml", "README.md",
    "streamlit_app.py",
]


def test_required_files_exist():
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    assert not missing, f"Faltan archivos: {missing}"


def test_env_is_gitignored():
    assert ".env" in (ROOT / ".gitignore").read_text().splitlines()


def test_at_least_two_examples_in_template():
    examples = (ROOT / "app/prompts/estimation/v1/examples.j2").read_text(encoding="utf-8")
    assert examples.count("### Ejemplo") >= 2