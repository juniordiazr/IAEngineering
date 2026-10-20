from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm_service import generate_estimation

router = APIRouter(tags=["estimations"])


class EstimationRequest(BaseModel):
    transcription: str = Field(..., min_length=10, description="Transcripción de la reunión")


class EstimationResponse(BaseModel):
    estimation: str
    model: str
    provider: str
    total_tokens: int | None = None


@router.post("/estimate", response_model=EstimationResponse)
async def estimate(request: EstimationRequest):
    try:
        return await generate_estimation(request.transcription)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error llamando al LLM: {exc}")