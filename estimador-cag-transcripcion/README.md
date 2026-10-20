# Transcripción de reunión – Proyecto 1 (Estimador CAG)

Repositorio con la transcripción de reunión que se usa como entrada del ejercicio
"Scaffolding del proyecto FastAPI" del curso AI Engineering.

## Contenido
- `transcripcion-reunion.md`: texto de la reunión con el cliente (entrada para `POST /api/v1/estimate`).

## Cómo usarla
Con el proyecto `estimador-cag` corriendo (`uv run uvicorn app.main:app --reload`),
en PowerShell:

    $ruta = "C:\Users\Junior\Documents\Git\IAEngineering\estimador-cag-transcripcion\ejemplos\transcripcion-reunion.md"
    $t = [string](Get-Content $ruta -Raw -Encoding UTF8)
    $body = @{ transcription = $t } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/estimate -ContentType "application/json; charset=utf-8" -Body $body

## Proyecto relacionado
Código del servicio: https://github.com/juniordiazr/IAEngineering (carpeta `estimador-cag`).