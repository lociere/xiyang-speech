"""Generate a short reference-conditioned WAV in the isolated TTS environment."""
import argparse
import json
import random
import sys
from pathlib import Path

from inference.config import ROOT, TTS_MODEL_DIR, TTS_SOURCE_DIR, TTS_INSTRUCTION
from inference.tts.resources import local_wetext_resources

PROMPT = "You are a helpful assistant.<|endofprompt|>希望你以后能够做的比我还好呦。"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=TTS_MODEL_DIR)
    parser.add_argument("--source-dir", type=Path, default=TTS_SOURCE_DIR)
    parser.add_argument("--prompt-audio", type=Path)
    parser.add_argument("--prompt-text", default=PROMPT)
    parser.add_argument("--mode", choices=("zero_shot", "instruct2"), default="zero_shot")
    parser.add_argument("--instruction", default=TTS_INSTRUCTION, help="Instruction for instruct2 mode")
    parser.add_argument("--text", default="你好，欢迎使用语音工具。")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed for comparable runs")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/checks/tts.wav")
    args = parser.parse_args()
    source = args.source_dir.resolve()
    model_dir = args.model_dir.resolve()
    prompt_audio = (args.prompt_audio or source / "asset/zero_shot_prompt.wav").resolve()
    if not (model_dir / "cosyvoice3.yaml").is_file():
        raise FileNotFoundError(
            f"找不到 TTS 模型配置：{model_dir / 'cosyvoice3.yaml'}；请按 docs/setup.md 下载。"
        )
    if not prompt_audio.is_file():
        raise FileNotFoundError(f"找不到参考录音：{prompt_audio}；请核对参考录音路径。")
    if not (source / "third_party/Matcha-TTS/matcha").is_dir():
        raise FileNotFoundError("请先递归初始化 CosyVoice 的 Matcha-TTS 子模块。")
    sys.path[:0] = [str(source), str(source / "third_party/Matcha-TTS")]

    import torch
    import numpy as np
    import soundfile as sf
    from cosyvoice.cli.cosyvoice import AutoModel

    if not torch.cuda.is_available():
        raise RuntimeError("当前验收配置要求 CUDA GPU，请检查驱动与 PyTorch。")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    with local_wetext_resources():
        model = AutoModel(model_dir=str(model_dir), fp16=True, load_trt=False, load_vllm=False)
    providers = model.frontend.speech_tokenizer_session.get_providers()
    if "CUDAExecutionProvider" not in providers:
        raise RuntimeError("语音 tokenizer 已回退到 CPU；请检查 ORT CUDA 构建和动态库。")
    if args.mode == "zero_shot":
        packets = model.inference_zero_shot(
            args.text, args.prompt_text, str(prompt_audio), stream=False
        )
    else:
        packets = model.inference_instruct2(
            args.text, args.instruction, str(prompt_audio), stream=False
        )
    chunks = [packet["tts_speech"].detach().cpu() for packet in packets]
    if not chunks:
        raise RuntimeError("TTS 没有生成音频。")
    audio = torch.cat(chunks, dim=-1)
    if not audio.numel() or not torch.isfinite(audio).all() or audio.abs().max().item() == 0:
        raise RuntimeError("TTS 音频为空、全静音或包含无效数值。")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(args.output), audio.squeeze(0).numpy(), model.sample_rate, subtype="PCM_16")
    report = {
        "output": str(args.output), "seconds": sf.info(str(args.output)).duration,
        "model_dir": str(model_dir), "llm_checkpoint": str(model_dir / "llm.pt"),
        "inference_mode": args.mode, "prompt_audio": str(prompt_audio),
        "text": args.text, "seed": args.seed,
        "prompt_text": args.prompt_text if args.mode == "zero_shot" else None,
        "instruction": args.instruction if args.mode == "instruct2" else None,
        "sample_rate": model.sample_rate, "torch": torch.__version__,
        "onnx_providers": providers, "text_normalizer": model.frontend.text_frontend or "basic",
        "scope": "reference-conditioned inference; listening and dialect evaluation still required",
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
