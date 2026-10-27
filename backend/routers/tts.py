"""Proxy TTS requests to the TTS worker running on a separate port."""
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.settings import Settings

router = APIRouter(prefix="/api", tags=["tts"])


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@router.post("/tts/synthesize")
async def synthesize(request: SynthesisRequest) -> Response:
    settings = Settings()
    url = f"{settings.tts_worker_url.rstrip('/')}/synthesize"

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url, json={"text": request.text})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="合成服务不可用，请确认已启动合成服务")

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=_extract_detail(response))

    return Response(
        content=response.content,
        media_type="audio/wav",
        headers={"Content-Disposition": 'attachment; filename="xiyang_speech.wav"'},
    )


def _extract_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str) and detail:
        return detail
    return response.text or f"合成失败（{response.status_code}）"
