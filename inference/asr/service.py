from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
import logging
import shutil
import tempfile

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from funasr import AutoModel


# 配置路径
ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models/asr/Fun-ASR-Nano-2512"
UPLOAD_DIR = ROOT / "runtime/uploads"

# 创建日志工具和锁
logger = logging.getLogger(__name__)
model_lock = Lock()


# 服务启动时加载模型，之后的请求复用这个模型
@asynccontextmanager
async def lifespan(app:FastAPI):
    if not (MODEL_DIR / "model.pt").is_file():
        raise RuntimeError(f"找不到模型：{MODEL_DIR}")

    if not torch.cuda.is_available():
        raise RuntimeError("当前环境无法使用CUDA GPU")

    UPLOAD_DIR.mkdir(parents=True,exist_ok=True)

    app.state.model = AutoModel(
        model=str(MODEL_DIR),
        device="cuda:0",
        disable_updata=True,
    )

    yield

    app.state.model = None


app = FastAPI(
    title="昔阳方言语音服务",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "worker": "asr"}


@app.post("/recognize")
def recognize(audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "").suffix.lower()

    if suffix not in {".wav", ".mp3", ".m4a", ".flac"}:
        raise HTTPException(
            status_code=400,
            detail="请上传 WAV、MP3、M4A 或 FLAC 录音",
        )

    temp_path = None

    try:
        # 为每次上传生成不同的临时文件名，避免互相覆盖
        with tempfile.NamedTemporaryFile(
            dir=UPLOAD_DIR,
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            shutil.copyfileobj(audio.file, temp_file)

        if temp_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="上传的文件为空")

        # 同一时间只让一个请求使用模型
        with model_lock, torch.inference_mode():
            result = app.state.model.generate(
                input=str(temp_path),
                language="中文",
                itn=True,
            )

        text = result[0].get("text", "").strip() if result else ""

        if not text:
            raise HTTPException(
                status_code=422,
                detail="没有识别出文字，请检查录音内容",
            )

        return {"text": text}

    except HTTPException:
        raise

    except Exception:
        logger.exception("语音识别失败")
        raise HTTPException(
            status_code=500,
            detail="识别失败，请检查录音或查看服务终端",
        )

    finally:
        # 识别结束后删除临时副本，原始录音不受影响
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)