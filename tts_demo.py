"""Generate a reference-conditioned WAV using CosyVoice instruct2."""
from pathlib import Path
import sys

import torch
import soundfile as sf


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "third_party/CosyVoice"

sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(SOURCE_DIR / "third_party/Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel


MODEL_DIR = ROOT / "models/tts/Fun-CosyVoice3-0.5B-2512"
REFERENCE_AUDIO = ROOT / "data/xiyang_prompt.wav"
OUTPUT_FILE = ROOT / "runtime/outputs/xiyang_instruct.wav"

TEXT = "今天天气不错，咱们吃完饭出去走走吧。"

INSTRUCTION = (
    "You are a helpful assistant. "
    "请用山西话表达。<|endofprompt|>"
)


if not (MODEL_DIR / "cosyvoice3.yaml").is_file():
    raise FileNotFoundError(f"找不到模型：{MODEL_DIR}")

if not REFERENCE_AUDIO.is_file():
    raise FileNotFoundError(f"找不到参考录音：{REFERENCE_AUDIO}")

if not torch.cuda.is_available():
    raise RuntimeError("当前环境无法使用 CUDA GPU")


model = AutoModel(
    model_dir=str(MODEL_DIR),
    fp16=True,
    load_trt=False,
    load_vllm=False,
)


audio_chunks = []

for result in model.inference_instruct2(
    tts_text=TEXT,
    instruct_text=INSTRUCTION,
    prompt_wav=str(REFERENCE_AUDIO),
    stream=False,
):
    audio_chunks.append(result["tts_speech"].detach().cpu())

if not audio_chunks:
    raise RuntimeError("模型没有返回音频")

audio = torch.cat(audio_chunks, dim=-1)


OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

sf.write(
    str(OUTPUT_FILE),
    audio.squeeze(0).float().numpy(),
    model.sample_rate,
    subtype="PCM_16",
)

print(f"生成完成：{OUTPUT_FILE}")
