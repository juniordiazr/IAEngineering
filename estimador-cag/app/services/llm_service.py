from openai import AsyncOpenAI

from app.config import settings
from app.context.examples import ESTIMATION_EXAMPLES

SYSTEM_INSTRUCTIONS = (
    "Eres un estimador de software experto. A partir de la transcripción de una "
    "reunión con un cliente, generas una estimación con desglose de tareas, horas, "
    "equipo recomendado y duración. Usa como referencia de formato y criterio las "
    "estimaciones previas que se incluyen a continuación. Responde en español y en Markdown."
)


def build_system_prompt() -> str:
    examples = "\n\n".join(
        f"### Ejemplo {i}\n**Resumen de la reunión:** {ex['meeting_summary']}\n"
        f"**Estimación:**\n{ex['estimation'].strip()}"
        for i, ex in enumerate(ESTIMATION_EXAMPLES, start=1)
    )
    return f"{SYSTEM_INSTRUCTIONS}\n\n## Estimaciones previas de referencia\n\n{examples}"


async def generate_estimation(transcription: str) -> dict:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": transcription},
        ],
        temperature=0.3,
    )
    return {
        "estimation": response.choices[0].message.content,
        "model": response.model,
        "provider": "openai",
        "total_tokens": response.usage.total_tokens if response.usage else None,
    }