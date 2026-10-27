"""Aggregate health of the model workers, for the frontend status bar."""
import httpx
from fastapi import APIRouter

from backend.settings import Settings

router = APIRouter(prefix="/api", tags=["health"])


async def _probe(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{base_url.rstrip('/')}/health")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


@router.get("/health")
async def worker_health() -> dict:
    settings = Settings()
    if settings.talk_mock:
        talk_ok = False
    else:
        talk_ok = await _probe(settings.talk_worker_url)

    return {
        "asr": await _probe(settings.asr_worker_url),
        "tts": await _probe(settings.tts_worker_url),
        "talk": talk_ok,
        "talk_mock": settings.talk_mock,
    }
