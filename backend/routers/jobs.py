"""Public job API. Only the scheduler starts GPU workers."""
import asyncio
import shutil
import warnings
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["jobs"])
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac"}


class SpeechInput(BaseModel):
    text: str = Field(min_length=1, max_length=300)


def runtime_for(request):
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or not runtime.accepting:
        raise HTTPException(503, "应用尚未就绪，请稍后重试")
    return runtime


async def save_upload(upload, directory, name, suffixes, limit):
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in suffixes:
        raise HTTPException(400, "文件格式不支持，请检查图片或录音格式")
    destination = directory / (name + suffix)
    size = 0
    with destination.open("wb") as target:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit * 1024 * 1024:
                raise HTTPException(413, f"文件不能超过 {limit} MB")
            target.write(chunk)
    if size == 0:
        raise HTTPException(400, "上传的文件为空")
    return str(destination)


def check_image(path):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.width * image.height > 12_000_000:
                    raise HTTPException(400, "图片请控制在 1200 万像素以内")
                image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise HTTPException(400, "图片无法读取，请上传完整的 JPG 或 PNG 图片") from exc


async def submit_files(request, kind, *, audio=None, image=None, text=""):
    runtime = runtime_for(request)
    job_id = uuid4().hex
    directory = runtime.store.directory / job_id
    directory.mkdir()
    payload = {"text": text} if text else {}
    try:
        if audio is not None:
            payload["audio"] = await save_upload(
                audio, directory, "audio", AUDIO_SUFFIXES, runtime.settings.max_audio_mb)
        if image is not None:
            payload["image"] = await save_upload(
                image, directory, "image", {".jpg", ".jpeg", ".png"},
                runtime.settings.max_image_mb)
            await asyncio.to_thread(check_image, payload["image"])
        return runtime.submit(kind, payload, job_id)
    except BaseException as exc:
        shutil.rmtree(directory, ignore_errors=True)
        if isinstance(exc, asyncio.QueueFull):
            raise HTTPException(429, "等待任务已满，请稍后提交") from exc
        if isinstance(exc, RuntimeError):
            raise HTTPException(503, str(exc)) from exc
        raise


@router.post("/asr/recognize", status_code=202)
async def recognize(request: Request, audio: UploadFile = File(...)):
    return await submit_files(request, "asr", audio=audio)


@router.post("/tts/synthesize", status_code=202)
async def synthesize(request: Request, body: SpeechInput):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "请输入需要生成的文字")
    return await submit_files(request, "tts", text=text)


@router.post("/talk", status_code=202)
async def talk(request: Request, image: UploadFile = File(...),
               text: str = Form(default=""), audio: UploadFile | None = File(default=None)):
    text = text.strip()
    if len(text) > 300:
        raise HTTPException(400, "文字最多 300 字")
    if bool(text) == bool(audio and audio.filename):
        raise HTTPException(400, "文字与音频必须选择且只能选择一种输入")
    return await submit_files(request, "talk", image=image, text=text,
                              audio=audio if audio and audio.filename else None)


@router.get("/jobs/{job_id}")
@router.get("/talk/{job_id}", include_in_schema=False)
def get_job(request: Request, job_id: str):
    job = runtime_for(request).public(job_id)
    if job is None:
        raise HTTPException(404, "任务不存在")
    return job


@router.get("/jobs/{job_id}/result")
@router.get("/talk/{job_id}/video", include_in_schema=False)
def get_result(request: Request, job_id: str):
    job = runtime_for(request).store.get(job_id)
    if job is None:
        raise HTTPException(404, "任务不存在")
    if job["status"] != "done":
        raise HTTPException(409, "任务尚未完成")
    if job["kind"] == "asr":
        return job["result"]
    path = Path(job["result_path"])
    if not path.is_file():
        raise HTTPException(410, "结果文件已被清理，请重新生成")
    media = "audio/wav" if job["kind"] == "tts" else "video/mp4"
    return FileResponse(path, media_type=media, filename=path.name)
