"""Convert recordings and export FunASR/CosyVoice manifests from reviewed TSV labels."""
import argparse
import csv
import json
import os
import subprocess
import wave
from pathlib import Path

FIELDS = ("id", "source", "text", "split", "checked")
SPLITS = ("train", "dev", "test")
ROOT = Path(__file__).resolve().parents[1]


def manifest_path(path):
    """Upstream readers resolve manifest paths from the repository working directory."""
    return Path(os.path.relpath(path, ROOT)).as_posix()


def read_labels(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    ids = set()
    for row in rows:
        key = row["id"]
        if not key.isascii() or not key.replace("_", "").isalnum() or key in ids:
            raise ValueError(f"ID 必须唯一且仅含 ASCII 字母、数字、下划线：{key}")
        ids.add(key)
        if row["split"] not in (*SPLITS, "exclude"):
            raise ValueError(f"无效 split：{row['split']}")
        if row["split"] != "exclude" and not row["text"].strip():
            raise ValueError(f"转写不能为空：{key}")
    return rows


def convert(source, destination, rate):
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.wav")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(source),
                        "-vn", "-ac", "1", "-ar", str(rate), "-c:a", "pcm_s16le",
                        str(temporary)], check=True)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def prepare(labels, output, *, allow_unreviewed=False):
    rows = read_labels(labels)
    selected = [row for row in rows if row["split"] in SPLITS]
    unchecked = [row["id"] for row in selected if row["checked"].lower() != "yes"]
    if unchecked and not allow_unreviewed:
        raise ValueError("请听录音核对 text 后，将 checked 改为 yes：" + ", ".join(unchecked))
    output = output.resolve()
    for row in rows:
        source = Path(row["source"])
        if not source.is_absolute():
            source = labels.parent / source
        if not source.is_file():
            raise FileNotFoundError(source)
        for rate, folder in ((16000, "wav16k"), (24000, "wav24k")):
            convert(source, output / folder / (row["id"] + ".wav"), rate)

    counts = {}
    for split in SPLITS:
        subset = [row for row in selected if row["split"] == split]
        counts[split] = len(subset)
        if not subset:
            raise ValueError(f"{split} 至少需要一条独立录音")
        records = []
        tts = output / "tts" / split
        tts.mkdir(parents=True, exist_ok=True)
        scp, texts, speakers, instructions = [], [], [], []
        for row in subset:
            key, text = row["id"], row["text"].strip()
            wav16 = output / "wav16k" / f"{key}.wav"
            wav24 = output / "wav24k" / f"{key}.wav"
            with wave.open(str(wav16)) as audio:
                duration = audio.getnframes() / audio.getframerate()
            if not 1 <= duration <= 30:
                raise ValueError(f"示例录音请切成 1–30 秒：{key} ({duration:g}s)")
            records.append({
                "key": key, "speech_length": round(duration * 100), "text_length": len(text),
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"语音转写：<|startofspeech|>!{manifest_path(wav16)}<|endofspeech|>"},
                    {"role": "assistant", "content": text},
                ],
            })
            scp.append(f"{key} {manifest_path(wav24)}")
            texts.append(f"{key} {text}")
            speakers.append(f"{key} xiyang_speaker01")
            instructions.append(f"{key} You are a helpful assistant.<|endofprompt|>")
        asr = output / "asr"
        asr.mkdir(exist_ok=True)
        (asr / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
        for name, lines in (("wav.scp", scp), ("text", texts), ("utt2spk", speakers),
                            ("instruct", instructions)):
            (tts / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        (tts / "spk2utt").write_text(
            "xiyang_speaker01 " + " ".join(row["id"] for row in subset) + "\n", encoding="utf-8")
    report = {"counts": counts, "unchecked": unchecked,
              "scope": "pipeline example; not a quality benchmark"}
    (output / "preparation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=Path("data/training_demo/labels.tsv"))
    parser.add_argument("--output", type=Path, default=Path("data/training_demo"))
    parser.add_argument("--allow-unreviewed", action="store_true", help="仅导出待核对预览；不可作为正式标签")
    args = parser.parse_args()
    prepare(args.labels.resolve(), args.output, allow_unreviewed=args.allow_unreviewed)


if __name__ == "__main__":
    main()
