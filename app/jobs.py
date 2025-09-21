import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class Job:
    id: str
    status: str = "pending"  # pending | running | completed | failed
    progress: int = 0  # 0..100
    stage: str = "init"
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


_registry: Dict[str, Job] = {}
_lock = asyncio.Lock()


async def create_job() -> Job:
    job_id = str(uuid.uuid4())
    job = Job(id=job_id)
    async with _lock:
        _registry[job_id] = job
    return job


async def update_job(job_id: str, *, status: Optional[str] = None, progress: Optional[int] = None, stage: Optional[str] = None, message: Optional[str] = None, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
    async with _lock:
        job = _registry.get(job_id)
        if not job:
            return
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = max(0, min(100, progress))
        if stage is not None:
            job.stage = stage
        if message is not None:
            job.message = message
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error


def get_job(job_id: str) -> Optional[Job]:
    return _registry.get(job_id)


def progress_callback_factory(job_id: str) -> Callable[[str, int, str], None]:
    def _cb(stage: str, pct: int, message: str) -> None:
        # fire-and-forget; schedule update to avoid awaiting in compute path
        asyncio.create_task(update_job(job_id, stage=stage, progress=pct, message=message, status="running"))
    return _cb


