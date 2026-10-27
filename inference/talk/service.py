"""Talking-head worker: image + text/audio -> lip-synced video via MuseTalk.

Runs in the ``MuseTalk`` conda environment on its own port. Text jobs generate dialect
audio through a short-lived ``xiyang-tts`` subprocess first, so CosyVoice and MuseTalk are
never resident at the same time (the host has limited RAM).
"""
import gc
import logging
import os
import queue
import subprocess
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from inference.talk.engine import MuseTalkEngine

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "runtime/outputs/talk"
TTS_SCRIPT = ROOT / "inference" / "talk" / "tts_cli.py"
TTS_PYTHON = os.environ.get(
    "XIYANG_TTS_PYTHON",
    str(Path.home() / "miniconda3" / "envs" / "xiyang-tts" / "bin" / "python"),
)
TTS_PREFIX = Path(TTS_PYTHON).resolve().parents[2]
_TTS_LD_LIBRARY_PATH = ":".join(
    [
        str(TTS_PREFIX / "lib/python3.10/site-packages/torch/lib"),
        str(TTS_PREFIX / "lib/python3.10/site-packages/nvidia/cudnn/lib"),
        str(TTS_PREFIX / "lib/python3.10/site-packages/nvidia/cublas/lib"),
        str(TTS_PREFIX / "lib/python3.10/site-packages/nvidia/cuda_runtime/lib"),
    ]
)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac"}

logger = logging.getLogger(__name__)

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_job_queue: queue.Queue[str] = queue.Queue()

_engine: MuseTalkEngine | None = None
_engine_lock = threading.Lock()


def _get_engine() -> MuseTalkEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            logger.info("loading MuseTalk engine ...")
            _engine = MuseTalkEngine(version="v15", use_float16=True)
            logger.info("MuseTalk engine loaded")
        return _engine


def _unload_engine() -> None:
    global _engine
    with _engine_lock:
        if _engine is not None:
            logger.info("unloading MuseTalk engine to free memory for TTS")
            _engine = None
            gc.collect()
            torch.cuda.empty_cache()


def _run_tts(text: str, output_path: str) -> str:
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = _TTS_LD_LIBRARY_PATH + ":" + env.get("LD_LIBRARY_PATH", "")
    logger.info("generating dialect audio via TTS subprocess")
    subprocess.run(
        [TTS_PYTHON, str(TTS_SCRIPT), text, output_path],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return output_path


def _process_job(job_id: str) -> None:
    job = _jobs[job_id]
    try:
        job["status"] = "running"
        job["progress"] = 3

        # 1. Resolve the audio input.
        if job.get("text"):
            job["progress"] = 5
            _unload_engine()
            audio_path = _run_tts(job["text"], str(OUTPUT_DIR / f"{job_id}_tts.wav"))
        else:
            audio_path = job["audio_path"]

        # 2. Generate the lip-synced video.
        job["progress"] = 20
        engine = _get_engine()

        def progress_cb(done: int, total: int) -> None:
            job["progress"] = 20 + int(75 * done / max(total, 1))

        engine.generate(
            str(job["image_path"]),
            str(audio_path),
            str(job["video_path"]),
            progress_cb=progress_cb,
        )

        job["status"] = "done"
        job["progress"] = 100
    except Exception as exc:
        logger.exception("talk job failed")
        job["status"] = "error"
        job["error"] = str(exc)
    finally:
        if job.get("text"):
            (OUTPUT_DIR / f"{job_id}_tts.wav").unlink(missing_ok=True)


def _worker_loop() -> None:
    while True:
        job_id = _job_queue.get()
        if job_id is None:
            break
        _process_job(job_id)
        _job_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=_worker_loop, daemon=True)
    thread.start()
    app.state.worker_thread = thread
    yield
    _job_queue.put(None)


app = FastAPI(title="昔阳方言说话人服务", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "worker": "talk"}


@app.post("/talk")
async def submit_talk(
    image: UploadFile = File(...),
    text: str = Form(default=""),
    audio: UploadFile | None = File(default=None),
) -> dict:
    if not (text.strip() or (audio is not None and audio.filename)):
        raise HTTPException(status_code=400, detail="请输入文字或上传一段音频")

    image_suffix = Path(image.filename or "").suffix.lower()
    if image_suffix not in _IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="请上传 JPG 或 PNG 图片")

    job_id = uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    image_path = job_dir / f"image{image_suffix}"
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传的图片为空")
    image_path.write_bytes(image_bytes)

    audio_path = None
    if audio is not None and audio.filename:
        audio_suffix = Path(audio.filename or "").suffix.lower()
        if audio_suffix not in _AUDIO_SUFFIXES:
            raise HTTPException(status_code=400, detail="音频仅支持 WAV、MP3、M4A 或 FLAC")
        audio_path = job_dir / f"audio{audio_suffix}"
        audio_path.write_bytes(await audio.read())

    job = {
        "status": "queued",
        "progress": 0,
        "error": None,
        "image_path": str(image_path),
        "audio_path": str(audio_path) if audio_path else None,
        "text": text.strip(),
        "video_path": str(job_dir / "output.mp4"),
    }
    with _jobs_lock:
        _jobs[job_id] = job
    _job_queue.put(job_id)

    return {"job_id": job_id}


@app.get("/talk/{job_id}")
def get_job(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    video_url = f"/talk/{job_id}/video" if job["status"] == "done" else None
    return {
        "status": job["status"],
        "progress": job["progress"],
        "error": job["error"],
        "video_url": video_url,
    }


@app.get("/talk/{job_id}/video")
def get_video(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    path = Path(job["video_path"])
    if job["status"] != "done" or not path.is_file():
        raise HTTPException(status_code=404, detail="视频尚未生成")
    return FileResponse(str(path), media_type="video/mp4", filename="xiyang_talk.mp4")
