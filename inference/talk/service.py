"""Private MuseTalk worker: one image/audio inference, no task orchestration."""
import asyncio
import logging
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from inference.config import OUTPUT_DIR

logger = logging.getLogger(__name__)
model_lock = Lock()


@asynccontextmanager
async def lifespan(app):
    from inference.talk.engine import MuseTalkEngine
    app.state.engine = await asyncio.to_thread(MuseTalkEngine, version="v15", use_float16=True)
    yield
    app.state.engine = None


app = FastAPI(title="MuseTalk worker", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "worker": "talk"}


@app.post("/generate", response_class=FileResponse)
def generate(image: UploadFile = File(...), audio: UploadFile = File(...)):
    # Public size/type checks run in the application before it starts this process.
    base = OUTPUT_DIR / "talk"
    base.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="request_", dir=base))
    try:
        image_path = directory / ("image" + Path(image.filename or "").suffix.lower())
        audio_path = directory / ("audio" + Path(audio.filename or "").suffix.lower())
        for upload, target in ((image, image_path), (audio, audio_path)):
            with target.open("wb") as output:
                shutil.copyfileobj(upload.file, output)
        video = directory / "video.mp4"
        with model_lock:
            app.state.engine.generate(str(image_path), str(audio_path), str(video))
        return FileResponse(video, media_type="video/mp4",
                            background=BackgroundTask(shutil.rmtree, directory, ignore_errors=True))
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        logger.exception("MuseTalk inference failed")
        detail = str(exc) if isinstance(exc, ValueError) else "口型视频生成失败，请查看 talk 日志"
        raise HTTPException(500, detail) from exc
