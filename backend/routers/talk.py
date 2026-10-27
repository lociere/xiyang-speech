"""Talking-head submission and status.

Mock implementation until the real talking-head worker lands: it fakes a
short-running job and renders a placeholder video with ffmpeg.
"""
from pathlib import Path
import subprocess
import threading
import time
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.settings import ROOT, Settings

router = APIRouter(prefix="/api", tags=["talk"])

_MOCK_DURATION = 3.0  # seconds the mock "processing" takes
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac"}

_jobs: dict[str, dict] = {}
_video_lock = threading.Lock()


@router.post("/talk")
async def submit_talk(
    image: UploadFile = File(...),
    text: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
) -> dict:
    settings = Settings()

    if not settings.talk_mock:
        raise HTTPException(status_code=503, detail="说话人服务尚未接入，请等待真实模型上线")

    if not (text.strip() or (audio is not None and audio.filename)):
        raise HTTPException(status_code=400, detail="请输入文字或上传一段音频")

    if Path(image.filename or "").suffix.lower() not in _IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="请上传 JPG 或 PNG 图片")

    if not await image.read():
        raise HTTPException(status_code=400, detail="上传的图片为空")

    if audio is not None and audio.filename:
        if Path(audio.filename or "").suffix.lower() not in _AUDIO_SUFFIXES:
            raise HTTPException(status_code=400, detail="音频仅支持 WAV、MP3、M4A 或 FLAC")

    job_id = uuid4().hex
    _jobs[job_id] = {
        "created_at": time.monotonic(),
        "image_name": image.filename or "image",
        "video_path": None,
    }
    return {"job_id": job_id}


@router.get("/talk/{job_id}")
def get_job(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    elapsed = time.monotonic() - job["created_at"]
    if elapsed >= _MOCK_DURATION:
        return {
            "status": "done",
            "progress": 100,
            "video_url": f"/api/talk/{job_id}/video",
            "error": None,
        }
    progress = max(1, int(elapsed / _MOCK_DURATION * 100))
    return {"status": "running", "progress": progress, "video_url": None, "error": None}


@router.get("/talk/{job_id}/video")
def get_video(job_id: str):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if time.monotonic() - job["created_at"] < _MOCK_DURATION:
        raise HTTPException(status_code=404, detail="视频尚未生成")

    if not job["video_path"]:
        with _video_lock:
            if not job["video_path"]:
                job["video_path"] = _render_mock_video(job_id)

    path = Path(job["video_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="视频文件缺失")
    return FileResponse(str(path), media_type="video/mp4", filename="xiyang_talk.mp4")


def _render_mock_video(job_id: str) -> str:
    output_dir = ROOT / "runtime/outputs/talk"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{job_id}.mp4"

    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=25",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="未找到 ffmpeg，无法生成演示视频")
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=503, detail=f"演示视频生成失败：{exc.stderr.strip()}")

    return str(path)
