from fastapi.testclient import TestClient
import httpx

from backend.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_endpoint_shape():
    response = _client().get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"asr", "tts", "talk", "talk_mock"}
    assert all(isinstance(data[key], bool) for key in data)


def test_asr_rejects_unsupported_file_type():
    response = _client().post(
        "/api/asr/recognize",
        files={"audio": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_tts_rejects_empty_text():
    response = _client().post("/api/tts/synthesize", json={"text": ""})
    assert response.status_code == 422


def test_talk_proxy_returns_502_when_worker_offline(monkeypatch):
    from backend.routers import talk

    original_client = httpx.AsyncClient

    def offline(request):
        raise httpx.ConnectError("worker offline", request=request)

    def client_factory(**kwargs):
        return original_client(transport=httpx.MockTransport(offline), **kwargs)

    monkeypatch.setattr(talk.httpx, "AsyncClient", client_factory)
    client = _client()
    submit = client.post(
        "/api/talk",
        files={"image": ("face.png", b"fake-image", "image/png")},
        data={"text": "你好"},
    )
    assert submit.status_code == 502

    status = client.get("/api/talk/doesnotexist")
    assert status.status_code == 502


def test_talk_result_uses_application_video_url(monkeypatch):
    from backend.routers import talk

    original_client = httpx.AsyncClient

    def response_for_worker(request):
        return httpx.Response(200, json={
            "status": "done", "progress": 100, "error": None,
            "video_url": "/talk/example/video",
        })

    def client_factory(**kwargs):
        return original_client(transport=httpx.MockTransport(response_for_worker), **kwargs)

    monkeypatch.setattr(talk.httpx, "AsyncClient", client_factory)
    response = _client().get("/api/talk/example")
    assert response.status_code == 200
    assert response.json()["video_url"] == "/api/talk/example/video"
