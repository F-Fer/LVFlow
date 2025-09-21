from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db_session, SessionLocal
from ..services import init_db, ingest_from_json, ingest_from_pdf
from ..jobs import create_job, update_job, progress_callback_factory


router = APIRouter()


class IngestResponse(BaseModel):
    inserted: dict[str, int]


@router.post("/init-db", summary="Create tables if not exist")
async def init_db_route(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    await init_db(session)
    return {"status": "created"}


@router.post("/from-json", response_model=IngestResponse)
async def ingest_from_json_route(
    offer_name: str,
    base_dir: str = "data",
    session: AsyncSession = Depends(get_db_session),
) -> IngestResponse:
    inserted = await ingest_from_json(session, offer_name=offer_name, base_dir=base_dir)
    return IngestResponse(inserted=inserted)

@router.post("/from-pdf")
async def ingest_from_pdf_route(
    offer_name: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    job = await create_job()
    pdf_bytes = await file.read()
    progress_cb = progress_callback_factory(job.id)

    async def _run() -> None:
        try:
            await update_job(job.id, status="running", stage="start", progress=1, message="Starting")
            # Use a fresh DB session not tied to the request lifecycle
            async with SessionLocal() as bg_session:
                inserted = await ingest_from_pdf(bg_session, offer_name=offer_name, pdf_bytes=pdf_bytes, progress_cb=progress_cb)
            await update_job(job.id, status="completed", progress=100, stage="done", result={"inserted": inserted})
        except Exception as e:
            await update_job(job.id, status="failed", stage="error", error=str(e))

    import asyncio
    asyncio.create_task(_run())
    return JSONResponse({"job_id": job.id})