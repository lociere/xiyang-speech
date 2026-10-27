from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from uuid import uuid4
import logging
import sys

import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "third_party/CosyVoice"

sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(SOURCE_DIR / "third_party/Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402


MODEL_DIR = ROOT / "models/tts/Fun-CosyVoice3-0.5B-2512"
REFERENCE_AUDIO = ROOT / "data/xiyang_prompt.wav"
OUTPUT_DIR = ROOT / "runtime/outputs/tts"


INSTRUCTION = (
    "You are a helpful assistant. "
    "请用山西话表达。<|endofprompt|>"
)

logger = logging.getLogger(__name__)
model_lock = Lock()


# 定义浏览器需要提交的数据
class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)


# 服务启动时加载模型
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not (MODEL_DIR / "cosyvoice3.yaml").is_file():
        raise RuntimeError(f"找不到模型：{MODEL_DIR}")

    if not REFERENCE_AUDIO.is_file():
        raise RuntimeError(f"找不到参考录音：{REFERENCE_AUDIO}")

    if not torch.cuda.is_available():
        raise RuntimeError("当前环境无法使用 CUDA GPU")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    app.state.model = AutoModel(
        model_dir=str(MODEL_DIR),
        fp16=True,
        load_trt=False,
        load_vllm=False,
    )

    yield

    app.state.model = None


app = FastAPI(
    title="昔阳方言语音生成服务",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "worker": "tts"}


@app.post(
    "/synthesize",
    response_class=FileResponse,
    responses={200: {"content": {"audio/wav": {}}}},
)
def synthesize(request: SynthesisRequest):
    text = request.text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="请输入需要生成语音的文字",
        )

    # 每次请求使用不同的文件名
    output_path = OUTPUT_DIR / f"{uuid4().hex}.wav"

    try:
        with model_lock:
            model = app.state.model
            audio_chunks = []

            for result in model.inference_instruct2(
                tts_text=text,
                instruct_text=INSTRUCTION,
                prompt_wav=str(REFERENCE_AUDIO),
                stream=False,
            ):
                audio_chunks.append(
                    result["tts_speech"].detach().cpu()
                )

            if not audio_chunks:
                raise RuntimeError("模型没有返回音频")

            audio = torch.cat(audio_chunks, dim=-1)

            sf.write(
                str(output_path),
                audio.squeeze(0).float().numpy(),
                model.sample_rate,
                subtype="PCM_16",
            )

        # 发送音频文件，发送完成后删除服务器上的临时副本
        return FileResponse(
            path=str(output_path),
            media_type="audio/wav",
            filename="xiyang_speech.wav",
            background=BackgroundTask(
                output_path.unlink,
                missing_ok=True,
            ),
        )

    except Exception:
        output_path.unlink(missing_ok=True)
        logger.exception("语音生成失败")

        raise HTTPException(
            status_code=500,
            detail="语音生成失败，请查看服务终端",
        )