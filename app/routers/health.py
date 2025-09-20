from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/ready", summary="Readiness probe")
def ready() -> dict:
    return {"status": "ok"}


@router.get("/live", summary="Liveness probe")
def live() -> dict:
    return {"status": "alive"}

