from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    "app/__init__.py", "app/main.py", "app/config.py",
    "app/routers/__init__.py", "app/routers/estimations.py",
    "app/services/__init__.py", "app/services/llm_service.py",
    "app/context/__init__.py", "app/context/examples.py",
    ".env.example", ".gitignore", "pyproject.toml", "README.md",
    "streamlit_app.py",
]


def test_required_files_exist():
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    assert not missing, f"Faltan archivos: {missing}"


def test_env_is_gitignored():
    assert ".env" in (ROOT / ".gitignore").read_text().splitlines()


def test_at_least_two_examples():
    from app.context.examples import ESTIMATION_EXAMPLES
    assert len(ESTIMATION_EXAMPLES) >= 2