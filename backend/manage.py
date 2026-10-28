"""One lifecycle entry point backed by Supervisor (Linux / WSL2)."""
import argparse
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from xmlrpc.client import ServerProxy

import httpx
from supervisor.xmlrpc import SupervisorTransport

from inference.config import ROOT  # loads .env before reading process configuration

STATE = ROOT / "runtime/processes"
CONFIG = STATE / "supervisord.conf"
SOCKET = STATE / "supervisor.sock"


def python_for(name: str) -> Path:
    if name == "app":
        default = str(Path(sys.executable).absolute())
    else:
        env_name = {"asr": "xiyang-asr", "tts": "xiyang-tts", "talk": "MuseTalk"}[name]
        default = str(Path(sys.prefix).parent / env_name / "bin/python")
    return Path(os.environ.get(f"XIYANG_{name.upper()}_PYTHON", default)).expanduser().absolute()


def worker_port(name: str) -> int:
    defaults = {"asr": 8101, "tts": 8102, "talk": 8103}
    url = urlparse(os.environ.get(
        f"XIYANG_{name.upper()}_WORKER_URL", f"http://127.0.0.1:{defaults[name]}"
    ))
    if (url.scheme != "http" or url.hostname != "127.0.0.1"
            or url.path not in ("", "/") or url.username or url.password
            or url.query or url.fragment):
        raise ValueError("统一启动只接受 http://127.0.0.1:端口 的本机 worker 地址")
    return url.port or 80


def render_config() -> str:
    def literal(value):
        return str(value).replace("%", "%%")
    lines = [
        "[unix_http_server]", f"file={literal(SOCKET)}", "chmod=0600",
        "[supervisord]", "nodaemon=true", f"pidfile={literal(STATE / 'supervisord.pid')}",
        f"logfile={literal(STATE / 'supervisord.log')}", "logfile_maxbytes=10MB",
        "logfile_backups=3", f"childlogdir={literal(STATE)}",
        "[rpcinterface:supervisor]", "supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface",
        "[supervisorctl]", f"serverurl=unix://{literal(SOCKET)}",
    ]
    for name in ("asr", "tts", "talk", "app"):
        python = python_for(name)
        if name == "app":
            command = [str(python), "-m", "uvicorn", "backend.main:app",
                       "--host", os.environ.get("XIYANG_HOST", "127.0.0.1"),
                       "--port", os.environ.get("XIYANG_PORT", "8000"), "--workers", "1"]
        else:
            command = [str(python), "-m", "inference.serve", name,
                       "--port", str(worker_port(name))]
        lines.extend([
            f"[program:{name}]", f"command={literal(shlex.join(command))}",
            f"directory={literal(ROOT)}",
            f"autostart={'true' if name == 'app' else 'false'}",
            f"autorestart={'unexpected' if name == 'app' else 'false'}",
            f"priority={200 if name == 'app' else 100}",
            f"startsecs={5 if name == 'app' else 0}",
            f"startretries={3 if name == 'app' else 0}",
            "stopsignal=TERM", "stopwaitsecs=60",
            "stopasgroup=true", "killasgroup=true", "redirect_stderr=true",
            f"stdout_logfile={literal(STATE / (name + '.log'))}",
            "stdout_logfile_maxbytes=10MB", "stdout_logfile_backups=3",
            'environment=PYTHONUNBUFFERED="1",OMP_NUM_THREADS="2"',
        ])
    return "\n".join(lines) + "\n"


def preflight() -> None:
    if sys.platform != "linux":
        raise ValueError("请在 Linux 或 WSL2 的 xiyang-app 环境运行")
    for command in ("ffmpeg", "ffprobe"):
        if not shutil.which(command):
            raise ValueError(f"缺少系统命令：{command}")
    from inference.config import ASR_MODEL_DIR, TTS_MODEL_DIR, TTS_SOURCE_DIR
    from inference.config import TALK_SOURCE_DIR, REFERENCE_AUDIO
    from inference.verify_models import MANIFEST, resource_locations
    required = [ASR_MODEL_DIR / "model.pt", TTS_MODEL_DIR / "cosyvoice3.yaml",
                TTS_SOURCE_DIR / "cosyvoice/cli/cosyvoice.py", REFERENCE_AUDIO,
                TTS_SOURCE_DIR / "third_party/Matcha-TTS/matcha/__init__.py"]
    for component, location in (("asr", ASR_MODEL_DIR), ("tts", TTS_MODEL_DIR),
                                ("talk", TALK_SOURCE_DIR / "models")):
        required += [location / item["path"] for item in MANIFEST["models"][component]["files"]]
    for name, spec in MANIFEST.get("resources", {}).items():
        required += [resource_locations()[name] / item["path"] for item in spec["files"]]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise ValueError("文件缺失；请按 docs/setup.md 安装：\n" + "\n".join(missing))
    for name in ("app", "asr", "tts", "talk"):
        python = python_for(name)
        if not python.is_file() or not os.access(python, os.X_OK):
            raise ValueError(f"{name} Python 不存在或不可执行：{python}")
        subprocess.run([str(python), "-m", "pip", "check"], check=True)
        subprocess.run([str(python), "-c", "import fastapi, uvicorn, dotenv"], check=True)
    ports = [int(os.environ.get("XIYANG_PORT", "8000"))]
    ports += [worker_port(n) for n in ("asr", "tts", "talk")]
    if len(set(ports)) != len(ports):
        raise ValueError("应用与三个 worker 的端口不能重复")
    for port in ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                raise ValueError(f"端口 {port} 已被占用，请先停止旧服务") from exc


def wait_ready(timeout: float) -> int:
    port = int(os.environ.get("XIYANG_PORT", "8000"))
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=3, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(f"http://127.0.0.1:{port}/ready")
                if response.status_code == 200:
                    print(f"项目已就绪，模型按需加载：http://localhost:{port}")
                    return 0
            except httpx.HTTPError:
                pass
            time.sleep(2)
    print("等待超时；查看 python -m backend.manage status 和 runtime/processes/*.log")
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status", "wait", "check"])
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    if args.action == "wait":
        return wait_ready(args.timeout)
    if args.action in ("stop", "status"):
        if not CONFIG.is_file():
            print("尚未生成启动配置，请先 start")
            return 1
        if args.action == "status":
            try:
                transport = SupervisorTransport(None, None, f"unix://{SOCKET}")
                with ServerProxy("http://localhost", transport=transport) as server:
                    processes = server.supervisor.getAllProcessInfo()
                for item in processes:
                    state = item["statename"]
                    note = "（按需待命）" if state == "STOPPED" and item["name"] != "app" else ""
                    print(f"{item['name']:8} {state:10} pid={item['pid']} {note}")
                return 0 if any(p["name"] == "app" and p["statename"] == "RUNNING"
                                for p in processes) else 1
            except (OSError, httpx.HTTPError) as exc:
                print(f"项目未运行或状态不可达：{exc}")
                return 1
        command = "shutdown"
        result = subprocess.call([sys.executable, "-m", "supervisor.supervisorctl",
                                  "-c", str(CONFIG), command])
        if result:
            return result
        # shutdown acknowledges the request before children actually exit.
        # Return only after the manager has finished stopping the project.
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            with socket.socket(socket.AF_UNIX) as probe:
                try:
                    probe.connect(str(SOCKET))
                except OSError:
                    print("项目已整体停止")
                    return 0
            time.sleep(0.2)
        print("等待停止超时，请检查 runtime/processes/supervisord.log", file=sys.stderr)
        return 1
    if SOCKET.exists():
        with socket.socket(socket.AF_UNIX) as probe:
            try:
                probe.connect(str(SOCKET))
            except OSError:
                pass
            else:
                print("项目已启动；请先 status 或 stop")
                return 1
    try:
        preflight()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"启动检查失败：{exc}", file=sys.stderr)
        return 1
    if args.action == "check":
        print("环境与必要文件检查通过；完整 SHA256 校验：python -m inference.verify_models")
        return 0
    STATE.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(render_config(), encoding="utf-8")
    print("正在启动项目：http://localhost:" + os.environ.get("XIYANG_PORT", "8000")
          + "；模型按需加载。按 Ctrl+C 停止整套项目。", flush=True)
    os.execv(sys.executable, [sys.executable, "-m", "supervisor.supervisord", "-c", str(CONFIG)])


if __name__ == "__main__":
    raise SystemExit(main())
