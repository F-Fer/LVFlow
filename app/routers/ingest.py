from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db_session
from ..services import init_db, ingest_from_json, ingest_from_pdf


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

@router.post("/from-pdf", response_model=IngestResponse)
async def ingest_from_pdf_route(
    offer_name: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> IngestResponse:
    pdf_bytes = await file.read()
    inserted = await ingest_from_pdf(session, offer_name=offer_name, pdf_bytes=pdf_bytes)
    return IngestResponse(inserted=inserted)

