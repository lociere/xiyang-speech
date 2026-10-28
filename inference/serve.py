"""Bootstrap a worker with its own CUDA libraries before Python imports torch."""
import argparse
import os
import sys
from pathlib import Path

from inference.config import ROOT


def library_paths(prefix: Path) -> list[str]:
    site = prefix / "lib/python3.10/site-packages"
    candidates = [site / "torch/lib", *sorted((site / "nvidia").glob("*/lib"))]
    return [str(p) for p in candidates if p.is_dir()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=["asr", "tts", "talk"])
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    env = os.environ.copy()
    libs = library_paths(Path(sys.prefix))
    if env.get("LD_LIBRARY_PATH"):
        libs.append(env["LD_LIBRARY_PATH"])
    env["LD_LIBRARY_PATH"] = ":".join(libs)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("OMP_NUM_THREADS", "2")
    os.chdir(ROOT)
    # exec, not an extra shell: Supervisor owns the actual uvicorn PID.
    os.execve(sys.executable, [
        sys.executable, "-m", "uvicorn", f"inference.{args.component}.service:app",
        "--host", "127.0.0.1", "--port", str(args.port), "--workers", "1",
    ], env)


if __name__ == "__main__":
    main()
