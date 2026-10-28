"""Shared, lightweight configuration: environment > .env > repository defaults."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


def path(name: str, default: str) -> Path:
    value = Path(os.environ.get("XIYANG_" + name, default)).expanduser()
    return (value if value.is_absolute() else ROOT / value).resolve()


ASR_MODEL_DIR = path("ASR_MODEL_DIR", "models/asr/Fun-ASR-Nano-2512")
TTS_MODEL_DIR = path("TTS_MODEL_DIR", "models/tts/Fun-CosyVoice3-0.5B-2512")
WETEXT_MODEL_DIR = path("WETEXT_MODEL_DIR", "models/tts/wetext")
TTS_SOURCE_DIR = path("TTS_SOURCE_DIR", "third_party/CosyVoice")
TALK_SOURCE_DIR = path("TALK_SOURCE_DIR", "third_party/MuseTalk")
REFERENCE_AUDIO = path("REFERENCE_AUDIO", "data/xiyang_prompt.wav")
OUTPUT_DIR = path("OUTPUT_DIR", "runtime/outputs")
UPLOAD_DIR = path("UPLOAD_DIR", "runtime/uploads")
TTS_INSTRUCTION = os.environ.get(
    "XIYANG_TTS_INSTRUCTION",
    "You are a helpful assistant. 请用山西话表达。<|endofprompt|>",
)
