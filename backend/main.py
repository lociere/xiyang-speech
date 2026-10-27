"""Application entry point: serves the frontend and proxies speech requests to workers."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.routers import asr, health, talk, tts
from backend.settings import ROOT


def create_app() -> FastAPI:
    app = FastAPI(title="昔阳方言语音工具", version="0.1.0")

    @app.get("/health", tags=["system"])
    def health_check() -> dict:
        return {"status": "ok", "stage": "foundation", "speech_api_ready": False}

    app.include_router(health.router)
    app.include_router(asr.router)
    app.include_router(tts.router)
    app.include_router(talk.router)

    app.mount("/", StaticFiles(directory=str(ROOT / "frontend"), html=True), name="frontend")

    return app


app = create_app()
