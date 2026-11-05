from fastapi import APIRouter, HTTPException

from app.prompts.loader import render_estimation_prompt
from app.schemas import EstimationRequest, EstimationResponse
from app.services.llm_service import generate_estimation

router = APIRouter(tags=["estimations"])

PROMPT_VERSION = "v1"


@router.post("/estimate", response_model=EstimationResponse)
async def estimate(request: EstimationRequest):
    system_prompt, user_prompt = render_estimation_prompt(request, version=PROMPT_VERSION)
    try:
        text = await generate_estimation(system_prompt, user_prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error llamando al LLM: {exc}")
    return EstimationResponse(text=text, prompt_version=PROMPT_VERSION)