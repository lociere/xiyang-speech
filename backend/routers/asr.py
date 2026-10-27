"""Proxy ASR requests to the ASR worker running on a separate port."""
from pathlib import Path

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.settings import Settings

router = APIRouter(prefix="/api", tags=["asr"])

_ALLOWED_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac"}


@router.post("/asr/recognize")
async def recognize(audio: UploadFile = File(...)) -> dict:
    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="请上传 WAV、MP3、M4A 或 FLAC 录音")

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    settings = Settings()
    url = f"{settings.asr_worker_url.rstrip('/')}/recognize"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                files={
                    "audio": (
                        audio.filename or "audio",
                        content,
                        audio.content_type or "application/octet-stream",
                    )
                },
            )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="识别服务不可用，请确认已启动识别服务")

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=_extract_detail(response))

    return response.json()


def _extract_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str) and detail:
        return detail
    return response.text or f"识别失败（{response.status_code}）"
