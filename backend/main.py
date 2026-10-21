"""Initial application entry point. Speech task endpoints are a later milestone."""
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="昔阳方言语音工具", version="0.1.0")

    @app.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok", "stage": "foundation", "speech_api_ready": False}

    return app


app = create_app()
