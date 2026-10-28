"""Application availability and model states; standby is a normal state."""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def worker_health(request: Request) -> dict:
    runtime = getattr(request.app.state, "runtime", None)
    available = runtime is not None and runtime.accepting
    return {
        "asr": available, "tts": available, "talk": available, "talk_mock": False,
        "models": runtime.models.states.copy() if runtime else {},
        "queued": runtime.queue.qsize() if runtime else 0,
        "active_job": runtime.active_job if runtime else None,
    }
