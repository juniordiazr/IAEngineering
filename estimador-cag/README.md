# Estimador CAG
API FastAPI que genera estimaciones de software desde transcripciones (arquitectura CAG).

## Setup
uv sync
copy .env.example .env   # y completa OPENAI_API_KEY

## Ejecutar
uv run uvicorn app.main:app --reload

## Probar

Usa la transcripción de https://github.com/juniordiazr/IAEngineering (carpeta `estimador-cag/ejemplos/transcripcion-reunion.md` como body de POST /api/v1/estimate en http://localhost:8000/docs.

O En Powershell: 
    $ruta = "C:\Users\Junior\Documents\Git\IAEngineering\estimador-cag-transcripcion\ejemplos\transcripcion-reunion.md"
    $t = [string](Get-Content $ruta -Raw -Encoding UTF8)
    $body = @{ transcription = $t } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/estimate -ContentType "application/json; charset=utf-8" -Body $body

## Tests
uv run pytest -v

## Interfaz de chat (Streamlit)
uv run streamlit run streamlit_app.py

Abre http://localhost:8501, pega la transcripción de la reunión y la estimación se muestra en streaming.
El panel lateral muestra el system prompt, el contexto CAG y las métricas de la última llamada.

