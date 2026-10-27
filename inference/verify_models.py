"""Verify local model files against the repository's SHA256 manifest; never download."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify_model(root: Path, spec: dict) -> int:
    base = (root / spec["local_dir"]).resolve()
    count = 0
    for item in spec["files"]:
        relative = Path(item["path"])
        path = (base / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(base):
            raise ValueError(f"模型清单含无效路径：{relative}")
        if not path.is_file() or path.stat().st_size != item["size"]:
            raise ValueError(f"模型文件缺失或大小不符：{path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != item["sha256"]:
            raise ValueError(f"模型文件 SHA256 不符：{path}")
        count += 1
        print(f"OK {spec['name']}/{relative}", flush=True)
    if count == 0:
        raise ValueError("模型清单为空。")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=["asr", "tts", "talk", "all"], default="all")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "config/models.json").read_text(encoding="utf-8"))
    for component, spec in manifest["models"].items():
        if args.component in ("all", component):
            print(f"{component}: {verify_model(ROOT, spec)} files verified", flush=True)


if __name__ == "__main__":
    main()
