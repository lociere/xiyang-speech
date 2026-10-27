"""Proxy talking-head requests to the MuseTalk worker running on a separate port."""
import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from backend.settings import Settings

router = APIRouter(prefix="/api", tags=["talk"])


def _extract_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str) and detail:
        return detail
    return response.text or f"请求失败（{response.status_code}）"


@router.post("/talk")
async def submit_talk(
    image: UploadFile = File(...),
    text: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
) -> dict:
    settings = Settings()
    files = {
        "image": (
            image.filename or "image",
            await image.read(),
            image.content_type or "application/octet-stream",
        )
    }
    data = {}
    if text.strip():
        data["text"] = text
    if audio is not None and audio.filename:
        files["audio"] = (
            audio.filename,
            await audio.read(),
            audio.content_type or "application/octet-stream",
        )

    url = f"{settings.talk_worker_url.rstrip('/')}/talk"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, data=data, files=files)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="说话人服务不可用，请确认已启动说话人服务")

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=_extract_detail(response))
    return response.json()


@router.get("/talk/{job_id}")
async def get_job(job_id: str) -> dict:
    settings = Settings()
    url = f"{settings.talk_worker_url.rstrip('/')}/talk/{job_id}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="说话人服务不可用，请确认已启动说话人服务")

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=_extract_detail(response))
    return response.json()


@router.get("/talk/{job_id}/video")
async def get_video(job_id: str):
    settings = Settings()
    url = f"{settings.talk_worker_url.rstrip('/')}/talk/{job_id}/video"
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="说话人服务不可用，请确认已启动说话人服务")

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=_extract_detail(response))
    return Response(
        content=response.content,
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="xiyang_talk.mp4"'},
    )
