import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


async def generate_estimation(system_prompt: str, user_prompt: str) -> str:
    if settings.llm_provider != "openai":
        raise ValueError(f"Proveedor no soportado todavía: {settings.llm_provider}")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    text = response.choices[0].message.content
    if not text:
        raise ValueError("El modelo devolvió una respuesta vacía")

    logger.info(
        "llm_call_completed model=%s total_tokens=%s",
        response.model,
        response.usage.total_tokens if response.usage else None,
    )
    return text