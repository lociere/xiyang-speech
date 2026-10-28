"""CLI that generates a dialect TTS wav from text.

Run in the ``xiyang-tts`` environment as a short-lived subprocess so that CosyVoice and
MuseTalk never stay resident at the same time. Usage::

    python inference/talk/tts_cli.py "<text>" "<output.wav>"
"""
import sys
from pathlib import Path

import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "third_party" / "CosyVoice"

sys.path.insert(0, str(SOURCE_DIR))
sys.path.insert(0, str(SOURCE_DIR / "third_party" / "Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

MODEL_DIR = ROOT / "models/tts/Fun-CosyVoice3-0.5B-2512"
REFERENCE_AUDIO = ROOT / "data/xiyang_prompt.wav"

INSTRUCTION = "You are a helpful assistant. 请用山西话表达。<|endofprompt|>"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: tts_cli.py <text> <output.wav>")
    text, output_path = sys.argv[1], sys.argv[2]

    model = AutoModel(model_dir=str(MODEL_DIR), fp16=True, load_trt=False, load_vllm=False)

    audio_chunks = []
    for result in model.inference_instruct2(
        tts_text=text,
        instruct_text=INSTRUCTION,
        prompt_wav=str(REFERENCE_AUDIO),
        stream=False,
    ):
        audio_chunks.append(result["tts_speech"].detach().cpu())

    if not audio_chunks:
        raise RuntimeError("TTS model returned no audio")

    audio = torch.cat(audio_chunks, dim=-1)
    sf.write(output_path, audio.squeeze(0).float().numpy(), model.sample_rate, subtype="PCM_16")
    print(output_path)


if __name__ == "__main__":
    main()
