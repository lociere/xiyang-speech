"""Run a real short ASR inference using only the installed FunASR package."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/asr/Fun-ASR-Nano-2512")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/checks/asr.json")
    args = parser.parse_args()
    model_dir = args.model_dir.resolve()
    audio = (args.audio or model_dir / "example/zh.mp3").resolve()
    if not (model_dir / "model.pt").is_file():
        raise FileNotFoundError(
            f"找不到 ASR 模型：{model_dir / 'model.pt'}；请按 docs/installation.md 下载。"
        )
    if not audio.is_file():
        raise FileNotFoundError(f"找不到输入录音：{audio}；请核对 --audio 后的路径和文件名。")

    import torch
    from funasr import AutoModel

    if not torch.cuda.is_available():
        raise RuntimeError("当前验收配置要求 CUDA GPU，请检查驱动与 PyTorch。")
    model = AutoModel(model=str(model_dir), device="cuda:0", disable_update=True)
    result = model.generate(input=str(audio), language="中文", itn=True)
    if not result or not result[0].get("text", "").strip():
        raise RuntimeError("ASR 没有返回有效文字。")
    report = {
        "text": result[0]["text"], "input": str(audio), "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0), "scope": "baseline inference only",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
