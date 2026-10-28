import asyncio
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import create_app
from backend.runtime import JobRuntime
from backend.settings import Settings


class StandbyModels:
    states = dict.fromkeys(("asr", "tts", "talk"), "standby")
    async def initialize(self):
        pass
    async def close(self):
        pass


def client(tmp_path):
    runtime = JobRuntime(Settings(_env_file=None, output_dir=tmp_path, max_queued_jobs=1),
                         models=StandbyModels())
    # Route tests deliberately leave queued jobs unexecuted; no GPU dependencies.
    runtime.accepting = True
    app = create_app()
    app.state.runtime = runtime
    return TestClient(app), runtime


def test_standby_is_available(tmp_path):
    api, runtime = client(tmp_path)
    data = api.get("/api/health").json()
    assert all(data[name] for name in ("asr", "tts", "talk"))
    assert data["models"]["asr"] == "standby"
    assert api.get("/ready").status_code == 200


def test_upload_validation_and_queue_limit(tmp_path):
    api, runtime = client(tmp_path)
    assert api.post("/api/asr/recognize", files={"audio": ("a.txt", b"a")}).status_code == 400
    assert api.post("/api/tts/synthesize", json={"text": ""}).status_code == 422
    assert api.post("/api/tts/synthesize", json={"text": "你好"}).status_code == 202
    assert api.post("/api/tts/synthesize", json={"text": "再见"}).status_code == 429
    assert sum(path.is_dir() for path in runtime.store.directory.iterdir()) == 1


def test_portrait_validation_and_exactly_one_audio_source(tmp_path):
    api, _ = client(tmp_path)
    image = BytesIO()
    Image.new("RGB", (20, 20)).save(image, format="PNG")
    files = {"image": ("face.png", image.getvalue(), "image/png")}
    assert api.post("/api/talk", files=files).status_code == 400
    assert api.post("/api/talk", files={"image": ("face.png", b"bad")}, data={"text": "你好"}).status_code == 400
    assert api.post("/api/talk", files=files, data={"text": "你好"}).status_code == 202


def test_result_survives_runtime_restart(tmp_path):
    api, runtime = client(tmp_path)
    job_id = runtime.submit("tts", {"text": "你好"})["job_id"]
    audio = tmp_path / "saved.wav"
    audio.write_bytes(b"wave-result")
    runtime.store.update(job_id, status="done", result_path=str(audio))
    restarted = JobRuntime(runtime.settings, models=StandbyModels())
    restarted.store.interrupt_pending()
    restarted.accepting = True
    api.app.state.runtime = restarted
    assert api.get(f"/api/jobs/{job_id}/result").content == b"wave-result"
    assert api.get("/api/jobs/missing").status_code == 404


def test_interrupted_jobs_fail_explicitly(tmp_path):
    _, runtime = client(tmp_path)
    job_id = runtime.submit("tts", {"text": "你好"})["job_id"]
    runtime.store.interrupt_pending()
    assert runtime.public(job_id)["status"] == "error"
    assert "重新提交" in runtime.public(job_id)["error"]


def test_model_switch_reuse_and_idle(tmp_path, monkeypatch):
    from backend.runtime import ModelManager

    class Controller:
        def __init__(self):
            self.events = []
        async def start(self, name):
            self.events.append(("start", name))
        async def stop(self, name):
            self.events.append(("stop", name))
        async def state(self, name):
            return "RUNNING"

    class Response:
        status_code = 200
    async def healthy(self, url, **kwargs):
        return Response()
    monkeypatch.setattr("httpx.AsyncClient.get", healthy)

    async def scenario():
        controller = Controller()
        models = ModelManager(Settings(_env_file=None, model_idle_seconds=0.01), controller)
        await models.initialize()
        controller.events.clear()
        async with models.use("tts"):
            pass
        async with models.use("tts"):
            pass
        async with models.use("talk"):
            pass
        assert controller.events == [("start", "tts"), ("stop", "tts"), ("start", "talk")]
        await asyncio.sleep(1.1)
        assert models.current is None
        assert controller.events[-1] == ("stop", "talk")
        await models.close()
    asyncio.run(scenario())


def test_failed_request_stops_model(monkeypatch):
    from backend.runtime import ModelManager
    class Controller:
        stopped = False
        async def stop(self, name):
            self.stopped = True
    async def scenario():
        controller = Controller()
        models = ModelManager(Settings(_env_file=None), controller)
        async def ensure(name):
            models.current = name
        models._ensure = ensure
        try:
            async with models.use("tts"):
                raise TimeoutError("timeout")
        except TimeoutError:
            pass
        assert controller.stopped and models.current is None
    asyncio.run(scenario())


def test_supervisor_does_not_autostart_models():
    from configparser import ConfigParser
    from backend.manage import render_config
    config = ConfigParser(interpolation=None)
    config.read_string(render_config())
    assert config.getboolean("program:app", "autostart")
    for model in ("asr", "tts", "talk"):
        assert not config.getboolean("program:" + model, "autostart")
        assert config["program:" + model]["autorestart"] == "false"


def test_serial_pipeline_and_recovery(tmp_path):
    from contextlib import asynccontextmanager
    import httpx

    class Models(StandbyModels):
        events = []
        @asynccontextmanager
        async def use(self, name):
            self.events.append(("enter", name))
            try:
                yield "http://worker"
            finally:
                self.events.append(("exit", name))

    async def scenario():
        models = Models()
        runtime = JobRuntime(Settings(_env_file=None, output_dir=tmp_path), models=models)
        async def no_probe(path):
            pass
        runtime._audio_duration = no_probe
        image = tmp_path / "face.png"
        image.write_bytes(b"test-fixture")
        async def post(self, url, **kwargs):
            if url.endswith("/synthesize"):
                return httpx.Response(200, content=b"audio")
            return httpx.Response(200, content=b"video")
        from unittest.mock import patch
        with patch("httpx.AsyncClient.post", post):
            await runtime.start()
            talk = runtime.submit("talk", {"image": str(image), "text": "你好"})["job_id"]
            # A bad input fails one job without killing the serial consumer.
            bad = runtime.submit("asr", {"audio": str(tmp_path / "missing.wav")})["job_id"]
            good = runtime.submit("tts", {"text": "再见"})["job_id"]
            await asyncio.wait_for(runtime.queue.join(), timeout=5)
            assert runtime.public(talk)["status"] == "done"
            assert runtime.public(bad)["status"] == "error"
            assert runtime.public(good)["status"] == "done"
            assert models.events[:4] == [
                ("enter", "tts"), ("exit", "tts"), ("enter", "talk"), ("exit", "talk")]
            assert Path(runtime.store.get(talk)["result_path"]).read_bytes() == b"video"
            await runtime.close()
    from pathlib import Path
    asyncio.run(scenario())


def test_shutdown_cancels_inflight_job(tmp_path):
    from contextlib import asynccontextmanager
    class Models(StandbyModels):
        closed = False
        @asynccontextmanager
        async def use(self, name):
            try:
                yield "http://worker"
            finally:
                self.closed = True

    async def scenario():
        models = Models()
        runtime = JobRuntime(Settings(_env_file=None, output_dir=tmp_path), models=models)
        entered = asyncio.Event()
        async def execute(job_id):
            async with models.use("tts"):
                entered.set()
                await asyncio.Event().wait()
        runtime._execute = execute
        await runtime.start()
        job = runtime.submit("tts", {"text": "你好"})["job_id"]
        await entered.wait()
        await asyncio.wait_for(runtime.close(), 2)
        assert models.closed and runtime.public(job)["status"] == "error"
    asyncio.run(scenario())
