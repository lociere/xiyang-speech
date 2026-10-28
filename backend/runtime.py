"""Single-host job scheduler and on-demand model process policy.

Supervisor owns process creation/termination. This module owns resource admission:
one active job and one resident model, reused until switch or idle expiry.
"""
import asyncio
import json
import logging
import sqlite3
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from uuid import uuid4
from xmlrpc.client import Fault, ServerProxy

import httpx
from supervisor.xmlrpc import SupervisorTransport

from backend.manage import SOCKET
from backend.settings import Settings

logger = logging.getLogger(__name__)
MODELS = ("asr", "tts", "talk")


class SupervisorController:
    async def call(self, method, *args):
        def invoke():
            transport = SupervisorTransport(None, None, f"unix://{SOCKET}")
            with ServerProxy("http://localhost", transport=transport) as server:
                return getattr(server.supervisor, method)(*args)
        return await asyncio.to_thread(invoke)

    async def start(self, name):
        await self.call("startProcess", name, False)

    async def stop(self, name):
        try:
            await self.call("stopProcess", name, True)
        except Fault as exc:
            # In SHUTDOWN, Supervisor itself stops every remaining process group.
            if exc.faultCode not in (6, 70):  # SHUTDOWN / NOT_RUNNING
                raise

    async def state(self, name):
        return (await self.call("getProcessInfo", name))["statename"]


class ModelManager:
    def __init__(self, settings, controller=None):
        self.settings = settings
        self.controller = controller or SupervisorController()
        self.current = None
        self.states = dict.fromkeys(MODELS, "standby")
        self.lock = asyncio.Lock()
        self.last_used = time.monotonic()
        self.reaper = None

    async def initialize(self):
        # On an application crash, Supervisor can still own an old model worker.
        # Stop it before admitting requests into the new application instance.
        for name in MODELS:
            await self.controller.stop(name)
        self.reaper = asyncio.create_task(self._reap())

    async def _stop(self):
        if self.current is None:
            return
        name = self.current
        self.states[name] = "stopping"
        await self.controller.stop(name)  # waits for process exit, then permits next load
        self.current = None
        self.states[name] = "standby"

    async def _ensure(self, name):
        if self.current == name and await self.controller.state(name) == "RUNNING":
            return
        await self._stop()
        self.current = name
        self.states[name] = "loading"
        await self.controller.start(name)
        deadline = time.monotonic() + self.settings.model_start_timeout
        url = getattr(self.settings, f"{name}_worker_url")
        async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
            while time.monotonic() < deadline:
                state = await self.controller.state(name)
                if state in ("EXITED", "FATAL", "STOPPED"):
                    raise RuntimeError(f"{name} 模型启动失败，请查看 runtime/processes/{name}.log")
                try:
                    response = await client.get(f"{url.rstrip('/')}/health")
                    if response.status_code == 200:
                        self.states[name] = "ready"
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.5)
        raise RuntimeError(f"{name} 模型加载超时，请查看对应模型日志")

    @asynccontextmanager
    async def use(self, name):
        # Also serializes idle expiry against an active request.
        async with self.lock:
            try:
                await self._ensure(name)
                self.states[name] = "busy"
                yield getattr(self.settings, f"{name}_worker_url").rstrip("/")
            except BaseException:
                # A timed-out request may still be running inside the worker.
                # Terminate it before allowing another job to use GPU resources.
                try:
                    await self._stop()
                except Exception:
                    logger.exception("Failed to stop model after job interruption")
                raise
            finally:
                self.last_used = time.monotonic()
                if self.current == name:
                    self.states[name] = "ready"
                if self.settings.model_idle_seconds == 0:
                    await self._stop()

    async def _reap(self):
        while True:
            await asyncio.sleep(1)
            if self.lock.locked():
                continue
            try:
                async with self.lock:
                    if self.current and (
                        time.monotonic() - self.last_used >= self.settings.model_idle_seconds
                        or await self.controller.state(self.current) != "RUNNING"
                    ):
                        await self._stop()
            except Exception:
                logger.exception("Idle model cleanup failed; retrying")

    async def close(self):
        if self.reaper:
            self.reaper.cancel()
            with suppress(asyncio.CancelledError):
                await self.reaper
        async with self.lock:
            await self._stop()


class JobStore:
    """Persistent job state; media files are stored in sibling task directories."""
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.database = directory / "jobs.sqlite3"
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT)")

    def get(self, job_id):
        with sqlite3.connect(self.database) as connection:
            row = connection.execute("SELECT data FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, job):
        with sqlite3.connect(self.database) as connection:
            connection.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?)",
                               (job["job_id"], json.dumps(job, ensure_ascii=False)))

    def update(self, job_id, **changes):
        job = self.get(job_id)
        job.update(changes)
        self.save(job)
        return job

    def interrupt_pending(self):
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute("SELECT data FROM jobs").fetchall()
        for row in rows:
            job = json.loads(row[0])
            if job["status"] not in ("done", "error"):
                self.update(job["job_id"], status="error", message="任务已中断",
                            error="应用已停止或重启，请重新提交任务")


class JobRuntime:
    def __init__(self, settings: Settings, models=None):
        self.settings = settings
        self.models = models or ModelManager(settings)
        self.store = JobStore(settings.output_dir / "jobs")
        self.queue = asyncio.Queue(maxsize=settings.max_queued_jobs)
        self.consumer = None
        self.accepting = False
        self.active_job = None

    async def start(self):
        self.store.interrupt_pending()
        await self.models.initialize()
        self.accepting = True
        self.consumer = asyncio.create_task(self._consume())

    def submit(self, kind, payload, job_id=None):
        if not self.accepting:
            raise RuntimeError("应用正在启动或停止，请稍后重试")
        if self.queue.full():
            raise asyncio.QueueFull
        job_id = job_id or uuid4().hex
        self.store.save({
            "job_id": job_id, "kind": kind, "payload": payload, "status": "queued",
            "progress": 0, "message": "排队等待中", "error": None,
            "result": None, "created_at": time.time(),
        })
        self.queue.put_nowait(job_id)
        return {"job_id": job_id}

    def public(self, job_id):
        job = self.store.get(job_id)
        if not job:
            return None
        result = {key: job[key] for key in (
            "job_id", "kind", "status", "progress", "message", "error", "result",
        )}
        result["result_url"] = f"/api/jobs/{job_id}/result" if job["status"] == "done" else None
        result["video_url"] = result["result_url"] if job["kind"] == "talk" else None
        return result

    async def _post(self, job_id, name, endpoint, message, progress, **kwargs):
        self.store.update(job_id, status="running", message=f"正在准备{message}模型",
                          progress=progress)
        async with self.models.use(name) as url:
            self.store.update(job_id, message=f"正在{message}")
            timeout = (self.settings.talk_inference_timeout if name == "talk"
                       else self.settings.inference_timeout)
            async with httpx.AsyncClient(timeout=timeout,
                                         trust_env=False) as client:
                try:
                    response = await client.post(url + endpoint, **kwargs)
                except httpx.TimeoutException as exc:
                    raise RuntimeError(
                        f"{message}超时（{timeout:g} 秒），请缩短输入或调整"
                        + (" XIYANG_TALK_INFERENCE_TIMEOUT" if name == "talk"
                           else " XIYANG_INFERENCE_TIMEOUT")
                    ) from exc
            if response.is_error:
                try:
                    detail = response.json()["detail"]
                except (ValueError, KeyError):
                    detail = f"{message}失败，请查看模型日志"
                raise RuntimeError(str(detail))
            return response

    async def _audio_duration(self, path):
        process = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), 15)
            duration = float(stdout)
            if process.returncode or not 0 < duration <= self.settings.max_audio_seconds:
                raise ValueError
        except (ValueError, asyncio.TimeoutError):
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise RuntimeError(f"录音无法读取或超过 {self.settings.max_audio_seconds:g} 秒")
        except asyncio.CancelledError:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise

    @staticmethod
    def _file(path):
        path = Path(path)
        return (path.name, path.read_bytes(), "application/octet-stream")

    async def _execute(self, job_id):
        job = self.store.get(job_id)
        data = job["payload"]
        directory = self.store.directory / job_id
        directory.mkdir(exist_ok=True)
        if data.get("audio"):
            await self._audio_duration(data["audio"])
        if job["kind"] == "asr":
            response = await self._post(
                job_id, "asr", "/recognize", "识别录音", 10,
                files={"audio": self._file(data["audio"])},
            )
            self.store.update(job_id, result=response.json())
            return
        if job["kind"] == "tts" or data.get("text"):
            response = await self._post(job_id, "tts", "/synthesize", "生成语音", 10,
                                        json={"text": data["text"]})
            audio = directory / "speech.wav"
            audio.write_bytes(response.content)
            if job["kind"] == "tts":
                self.store.update(job_id, result_path=str(audio))
                return
            data["audio"] = str(audio)
            await self._audio_duration(audio)
        response = await self._post(
            job_id, "talk", "/generate", "生成口型视频", 55,
            files={"image": self._file(data["image"]), "audio": self._file(data["audio"])},
        )
        video = directory / "video.mp4"
        video.write_bytes(response.content)
        self.store.update(job_id, result_path=str(video))

    async def _consume(self):
        while True:
            job_id = await self.queue.get()
            self.active_job = job_id
            try:
                await self._execute(job_id)
                self.store.update(job_id, status="done", progress=100, message="已完成")
            except asyncio.CancelledError:
                self.store.update(job_id, status="error", message="任务已中断",
                                  error="应用已停止，请重新提交任务")
                raise
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                if isinstance(exc, httpx.TimeoutException):
                    detail = "模型推理超时，请缩短输入或查看对应模型日志"
                elif isinstance(exc, httpx.HTTPError):
                    detail = "模型进程连接中断，请重试或查看对应模型日志"
                else:
                    detail = str(exc)
                self.store.update(job_id, status="error", message="任务失败", error=detail)
            finally:
                self.active_job = None
                self.queue.task_done()

    async def close(self):
        self.accepting = False
        if self.consumer:
            self.consumer.cancel()
            with suppress(asyncio.CancelledError):
                await self.consumer
        try:
            await self.models.close()
        finally:
            self.store.interrupt_pending()
