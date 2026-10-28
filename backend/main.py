"""Application lifecycle, task API and same-origin frontend."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import health, jobs
from backend.runtime import JobRuntime
from backend.settings import ROOT, Settings


def create_app(runtime_factory=JobRuntime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        runtime = runtime_factory(Settings())
        app.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(title="昔阳方言语音工具", version="0.1.0", lifespan=lifespan)

    @app.get("/health", tags=["system"])
    def health_check() -> dict:
        return {"status": "ok"}

    @app.get("/ready", tags=["system"])
    def readiness():
        runtime = getattr(app.state, "runtime", None)
        ready = runtime is not None and runtime.accepting
        return JSONResponse({"status": "ready" if ready else "not_ready"},
                            status_code=200 if ready else 503)

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.mount("/", StaticFiles(directory=str(ROOT / "frontend"), html=True), name="frontend")
    return app


app = create_app()
